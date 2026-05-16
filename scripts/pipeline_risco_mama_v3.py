# Nome no Repositorio: pipeline_risco_mama_v3.py
# Objetivo: Pipeline de risco mama com engenharia base e inferência por cadeias clínicas.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import pandas as pd

try:
    from clinical_chain_detector import (
        ClinicalChainDetector,
        FLAGS_NOVAS_PARA_SCORE,
        TUSS_BRCA,
        TimelineBuilder,
    )
except ImportError:  # pragma: no cover
    from scripts.clinical_chain_detector import (
        ClinicalChainDetector,
        FLAGS_NOVAS_PARA_SCORE,
        TUSS_BRCA,
        TimelineBuilder,
    )

logger = logging.getLogger(__name__)


PADROES_FEATURES_BASE: Dict[str, List[str]] = {
    "MAMOGRAFIA_REALIZADA": ["MAMOGRAFIA"],
    "ULTRASSOM_MAMARIO_REALIZADO": ["ULTRASSOM MAM", "ECOGRAF MAM", "US MAM"],
    "BIOPSIA_MAMARIA_REALIZADA": [
        "BIOPS",
        "CORE BIOPSY",
        "AGULHA GROSSA",
        "PUNCAO ASPIRATIVA",
        "PAAF",
    ],
    "TESTE_BRCA_REALIZADO": TUSS_BRCA,
    "RNM_MAMARIA_REALIZADA": ["RESSONANCIA MAMARIA", "RNM MAM"],
    "MASTECTOMIA_PROFILATICA_REALIZADA": ["MASTECTOMIA PROFILAT"],
}
FLAGS_BASE_PARA_SCORE = list(PADROES_FEATURES_BASE) + ["IDADE_MAIOR_50"]
TERMOS_RELEVANTES_BASE = sorted(
    {termo for termos in PADROES_FEATURES_BASE.values() for termo in termos}
)


@dataclass
class ConfigLoader:
    pesos: Dict[str, int] = field(default_factory=dict)
    limites_faixa: Dict[str, int] = field(
        default_factory=lambda: {
            "MODERADO": 20,
            "ALTO": 50,
            "MUITO_ALTO": 90,
        }
    )

    def __post_init__(self) -> None:
        pesos_padrao = ClinicalChainDetector.PESOS_ESTIMADOS.copy()
        pesos_padrao.update(self.pesos)
        self.pesos = pesos_padrao

    def peso(self, flag: str) -> int:
        return int(self.pesos.get(flag, 0))

    def yaml_snippet(self) -> str:
        linhas = ["pesos:"]
        for flag, peso in self.pesos.items():
            linhas.append(f"  {flag}: {peso}")
        return "\n".join(linhas)


class FeatureEngineer:
    def __init__(self, cfg: Optional[ConfigLoader] = None) -> None:
        self.cfg = cfg or ConfigLoader()

    @staticmethod
    def _normalizar_usuarios(df_usuarios: pd.DataFrame) -> pd.DataFrame:
        df = df_usuarios.copy()
        if "ID_USUARIO" not in df.columns:
            raise ValueError("df_usuarios precisa ter a coluna ID_USUARIO.")

        df["ID_USUARIO"] = df["ID_USUARIO"].astype(str).str.strip()
        if "IDADE_USU" not in df.columns and "IDADE" in df.columns:
            df["IDADE_USU"] = df["IDADE"]
        if "SEXO" in df.columns:
            df["SEXO"] = df["SEXO"].fillna("").astype(str).str.upper().str.strip()
        if "IDADE_USU" in df.columns:
            df["IDADE_USU"] = pd.to_numeric(df["IDADE_USU"], errors="coerce")
            df["IDADE_MAIOR_50"] = (df["IDADE_USU"] >= 50).fillna(False).astype(int)
        else:
            df["IDADE_MAIOR_50"] = 0
        return df

    @staticmethod
    def _match_any(grupo: pd.DataFrame, termos: Iterable[str]) -> int:
        return int(
            grupo.apply(
                lambda row: any(
                    termo in row["SERVICO_UPPER"] or termo in row["CODIGO_SERVICO"]
                    for termo in termos
                ),
                axis=1,
            ).any()
        )

    @staticmethod
    def _count_any(grupo: pd.DataFrame, termos: Iterable[str]) -> int:
        return int(
            grupo.apply(
                lambda row: any(
                    termo in row["SERVICO_UPPER"] or termo in row["CODIGO_SERVICO"]
                    for termo in termos
                ),
                axis=1,
            ).sum()
        )

    def build(
        self,
        df_producao: pd.DataFrame,
        df_usuarios: pd.DataFrame,
    ) -> pd.DataFrame:
        usuarios = self._normalizar_usuarios(df_usuarios)
        timeline = TimelineBuilder(df_producao).build()

        base = usuarios[
            [col for col in ["ID_USUARIO", "IDADE_USU", "SEXO", "IDADE_MAIOR_50"] if col in usuarios.columns]
        ].drop_duplicates("ID_USUARIO")

        if timeline.empty:
            for flag in PADROES_FEATURES_BASE:
                base[flag] = 0
            base["QTD_EVENTOS_MAMA"] = 0
            return base

        flags = {}
        for uid, grupo in timeline.groupby("ID_USUARIO"):
            flags[uid] = {
                flag: self._match_any(grupo, termos)
                for flag, termos in PADROES_FEATURES_BASE.items()
            }
            flags[uid]["QTD_EVENTOS_MAMA"] = self._count_any(
                grupo, TERMOS_RELEVANTES_BASE
            )

        df_flags = (
            pd.DataFrame.from_dict(flags, orient="index")
            .reset_index()
            .rename(columns={"index": "ID_USUARIO"})
        )

        resultado = base.merge(df_flags, on="ID_USUARIO", how="outer")
        colunas_flags = list(PADROES_FEATURES_BASE) + ["IDADE_MAIOR_50"]
        for coluna in colunas_flags:
            if coluna in resultado.columns:
                resultado[coluna] = resultado[coluna].fillna(0).astype(int)
        if "QTD_EVENTOS_MAMA" in resultado.columns:
            resultado["QTD_EVENTOS_MAMA"] = (
                pd.to_numeric(resultado["QTD_EVENTOS_MAMA"], errors="coerce")
                .fillna(0)
                .astype(int)
            )
        return resultado


class RiscoMamaPipeline:
    _FLAGS_SCORE_BASE: List[str] = FLAGS_BASE_PARA_SCORE

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        flags_score_base: Optional[List[str]] = None,
    ) -> None:
        self.cfg = config or ConfigLoader()
        self.feature_engineer = FeatureEngineer(cfg=self.cfg)
        self.detector = ClinicalChainDetector(config=self.cfg)
        self._flags_score_base = list(flags_score_base or self._FLAGS_SCORE_BASE)
        self._flags_score = list(dict.fromkeys(self._flags_score_base + FLAGS_NOVAS_PARA_SCORE))

    @property
    def flags_score(self) -> List[str]:
        return self._flags_score

    def _calcular_score(self, df: pd.DataFrame) -> pd.DataFrame:
        score = pd.Series(0, index=df.index, dtype=int)
        motivos = []

        for flag in self._flags_score:
            if flag not in df.columns:
                logger.warning("Flag configurada para score não encontrada no DataFrame: %s", flag)
                continue
            valor = pd.to_numeric(df[flag], errors="coerce").fillna(0).astype(int)
            peso = self.cfg.peso(flag)
            score = score + (valor * peso)
            if peso:
                motivos.append(
                    [f"{flag}({peso})" if ativo and peso else "" for ativo in valor]
                )

        df["SCORE_RISCO_MAMA"] = score
        if motivos:
            df["MOTIVOS_SCORE"] = [
                ", ".join([item for item in linha if item])
                for linha in zip(*motivos)
            ]
        else:
            df["MOTIVOS_SCORE"] = ""
        return df

    def _classificar_risco(self, score: int) -> str:
        if score >= self.cfg.limites_faixa["MUITO_ALTO"]:
            return "MUITO_ALTO"
        if score >= self.cfg.limites_faixa["ALTO"]:
            return "ALTO"
        if score >= self.cfg.limites_faixa["MODERADO"]:
            return "MODERADO"
        return "BAIXO"

    def run(
        self,
        df_producao: pd.DataFrame,
        df_usuarios: pd.DataFrame,
    ) -> pd.DataFrame:
        df = self.feature_engineer.build(
            df_producao=df_producao,
            df_usuarios=df_usuarios,
        )

        df_chains = self.detector.detectar(
            df_producao=df_producao,
            df_usuarios=df_usuarios,
        )
        df = df.merge(df_chains, on="ID_USUARIO", how="left")
        df[self.detector.FLAGS] = df[self.detector.FLAGS].fillna(0).astype(int)
        df = self._calcular_score(df)
        df["FAIXA_RISCO_MAMA"] = df["SCORE_RISCO_MAMA"].apply(self._classificar_risco)
        colunas_ordem = ["SCORE_RISCO_MAMA"]
        ascendente = [False]
        if "QTD_EVENTOS_MAMA" in df.columns:
            colunas_ordem.append("QTD_EVENTOS_MAMA")
            ascendente.append(False)
        return df.sort_values(by=colunas_ordem, ascending=ascendente).reset_index(
            drop=True
        )

    def resumo_flags(self, df_resultado: pd.DataFrame) -> pd.DataFrame:
        return self.detector.resumo(df_resultado)

    def yaml_snippet(self) -> str:
        return self.cfg.yaml_snippet()


if __name__ == "__main__":
    df_prod_mock = pd.DataFrame(
        [
            {
                "ID_USUARIO": "U001",
                "DATA_ATENDIMENTO": "2024-01-10",
                "SERVICO": "MAMOGRAFIA BILATERAL",
                "CODIGO_SERVICO": "40301366",
            },
            {
                "ID_USUARIO": "U001",
                "DATA_ATENDIMENTO": "2024-02-20",
                "SERVICO": "BIOPSIA CORE BIOPSY MAMA",
                "CODIGO_SERVICO": "40307360",
            },
            {
                "ID_USUARIO": "U003",
                "DATA_ATENDIMENTO": "2024-03-01",
                "SERVICO": "SEQUENCIAMENTO GENETICO BRCA1 BRCA2",
                "CODIGO_SERVICO": "40313171",
            },
            {
                "ID_USUARIO": "U003",
                "DATA_ATENDIMENTO": "2024-05-15",
                "SERVICO": "MASTECTOMIA PROFILATICA BILATERAL",
                "CODIGO_SERVICO": "30903027",
            },
            {
                "ID_USUARIO": "U004",
                "DATA_ATENDIMENTO": "2020-07-12",
                "SERVICO": "PARTO CESARIA",
                "CODIGO_SERVICO": "31309135",
            },
        ]
    )
    df_usuarios_mock = pd.DataFrame(
        [
            {"ID_USUARIO": "U001", "IDADE_USU": 52, "SEXO": "F"},
            {"ID_USUARIO": "U003", "IDADE_USU": 38, "SEXO": "F"},
            {"ID_USUARIO": "U004", "IDADE_USU": 39, "SEXO": "F"},
        ]
    )

    pipeline = RiscoMamaPipeline()
    resultado = pipeline.run(df_prod_mock, df_usuarios_mock)
    print(resultado.to_string(index=False))
    print(pipeline.resumo_flags(resultado).to_string(index=False))
