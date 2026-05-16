# Nome no Repositório: clinical_chain_detector.py
# Objetivo: Inferir sinais clínicos de risco mama por cadeia temporal de eventos.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CadeiaConfig:
    nome: str
    flag_saida: str
    descricao: str
    peso_estimado: int
    etapas: List[Tuple[List[str], int]] = field(default_factory=list)
    apenas_primeiro_evento_tipo: Optional[str] = None


CADEIAS_PADRAO: List[CadeiaConfig] = [
    CadeiaConfig(
        nome="Mamografia com Resultado Suspeito Inferido",
        flag_saida="MAMOGRAFIA_RESULTADO_INFERIDO_ALTERADO",
        descricao=(
            "Mamografia seguida de biópsia ou ultrassonografia mamária em até 60 dias. "
            "Indica resultado provável alterado."
        ),
        peso_estimado=20,
        etapas=[
            (["MAMOGRAFIA"], 0),
            (
                [
                    "BIOPS",
                    "ULTRASSOM",
                    "ECOGRAF",
                    "CORE BIOPSY",
                    "AGULHA GROSSA",
                    "PUNCAO ASPIRATIVA",
                    "PAAF",
                    "RESSONANCIA MAMARIA",
                    "RNM MAM",
                ],
                60,
            ),
        ],
    ),
    CadeiaConfig(
        nome="BRCA Positivo Inferido",
        flag_saida="BRCA_POSITIVO_INFERIDO",
        descricao=(
            "Teste BRCA seguido de genética clínica ou mastectomia profilática "
            "em até 90 dias."
        ),
        peso_estimado=70,
        etapas=[
            (
                [
                    "BRCA",
                    "SEQUENCIAMENTO GENETICO",
                    "PAINEL GENETICO",
                    "GENE BRCA",
                    "TESTE HEREDITARIO",
                ],
                0,
            ),
            (
                [
                    "GENETIC",
                    "MASTECTOMIA PROFILAT",
                    "SALPINGO",
                    "OOFORECTOMIA",
                    "ACONSELHAMENTO GENETIC",
                ],
                90,
            ),
        ],
    ),
    CadeiaConfig(
        nome="Cadeia de Investigação Oncológica Progressiva",
        flag_saida="CADEIA_INVESTIGACAO_ONCOLOGICA",
        descricao=(
            "Mamografia seguida de ultrassom mamário e biópsia em até 90 dias."
        ),
        peso_estimado=35,
        etapas=[
            (["MAMOGRAFIA"], 0),
            (["ULTRASSOM MAM", "ECOGRAF MAM", "US MAM"], 45),
            (
                [
                    "BIOPS",
                    "CORE BIOPSY",
                    "AGULHA GROSSA",
                    "PUNCAO ASPIRATIVA",
                    "PAAF",
                ],
                45,
            ),
        ],
    ),
    CadeiaConfig(
        nome="Investigação Pós-BRCA",
        flag_saida="INVESTIGACAO_POS_BRCA",
        descricao=(
            "Teste BRCA seguido de RNM mamária ou mamografia adicional em até 180 dias."
        ),
        peso_estimado=40,
        etapas=[
            (["BRCA", "SEQUENCIAMENTO GENETICO", "PAINEL GENETICO"], 0),
            (["RESSONANCIA MAMARIA", "RNM MAM", "MAMOGRAFIA"], 180),
        ],
    ),
]

PARTO_TARDIO_CONFIG = CadeiaConfig(
    nome="Parto Primíparo Após os 30 Anos",
    flag_saida="PARTO_PRIMIPARO_APOS_30",
    descricao=(
        "Primeiro parto registrado quando a beneficiária tinha mais de 30 anos."
    ),
    peso_estimado=12,
    etapas=[],
    apenas_primeiro_evento_tipo="PARTO",
)

TERMOS_PARTO = [
    "PARTO NORMAL",
    "PARTO CESARIA",
    "CESAREA",
    "PARTO A TERMO",
    "ASSISTENCIA AO PARTO",
    "PARTO VAGINAL",
    "CESAREO",
    "PARTO PREMATURO",
    "RESOLUCAO OBSTETRICA",
]

TUSS_BRCA = [
    "40313171",
    "40313198",
    "40313201",
    "BRCA",
    "SEQUENCIAMENTO GENETICO",
    "PAINEL GENETICO",
    "PAINEL HEREDITARIO",
    "GENE BRCA",
]


class TimelineBuilder:
    COLUNAS_CANDIDATAS = {
        "id_usuario": ["ID_USUARIO_LIMPO", "ID_USUARIO"],
        "data_atendimento": ["DATA_ATENDIMENTO", "DATA_ATENDIMENTO_FATO_PRO"],
        "servico": ["SERVICO"],
        "codigo_servico": ["CODIGO_SERVICO"],
    }

    def __init__(self, df_producao: pd.DataFrame) -> None:
        self.df = df_producao.copy()

    def _resolver_coluna(self, opcoes: List[str]) -> Optional[str]:
        for coluna in opcoes:
            if coluna in self.df.columns:
                return coluna
        return None

    @staticmethod
    def _normalizar_texto(serie: pd.Series) -> pd.Series:
        return (
            serie.fillna("")
            .astype(str)
            .str.normalize("NFKD")
            .str.encode("ascii", errors="ignore")
            .str.decode("utf-8")
            .str.upper()
            .str.strip()
        )

    def build(self) -> pd.DataFrame:
        id_col = self._resolver_coluna(self.COLUNAS_CANDIDATAS["id_usuario"])
        data_col = self._resolver_coluna(self.COLUNAS_CANDIDATAS["data_atendimento"])
        servico_col = self._resolver_coluna(self.COLUNAS_CANDIDATAS["servico"])
        codigo_col = self._resolver_coluna(self.COLUNAS_CANDIDATAS["codigo_servico"])

        if not id_col or not data_col or not servico_col:
            raise ValueError(
                "df_producao precisa ter colunas de usuário, data e serviço para detecção."
            )

        df = self.df[[id_col, data_col, servico_col]].copy()
        if codigo_col:
            df[codigo_col] = self.df[codigo_col]
        else:
            df["CODIGO_SERVICO"] = ""
            codigo_col = "CODIGO_SERVICO"

        df = df.rename(
            columns={
                id_col: "ID_USUARIO",
                data_col: "DATA_ATENDIMENTO",
                servico_col: "SERVICO",
                codigo_col: "CODIGO_SERVICO",
            }
        )
        df["DATA_ATENDIMENTO"] = pd.to_datetime(
            df["DATA_ATENDIMENTO"], errors="coerce"
        ).dt.date
        df = df.dropna(subset=["ID_USUARIO", "DATA_ATENDIMENTO"])
        df["ID_USUARIO"] = df["ID_USUARIO"].astype(str).str.strip()
        df["SERVICO_UPPER"] = self._normalizar_texto(df["SERVICO"])
        df["CODIGO_SERVICO"] = self._normalizar_texto(df["CODIGO_SERVICO"])
        return df.sort_values(["ID_USUARIO", "DATA_ATENDIMENTO"]).reset_index(drop=True)


class ChainMatcher:
    def __init__(self, config: CadeiaConfig) -> None:
        self.config = config

    @staticmethod
    def _match_etapa(servico: str, codigo: str, termos: List[str]) -> bool:
        return any(termo in servico or termo in codigo for termo in termos)

    def detectar_usuario(self, eventos: pd.DataFrame) -> bool:
        if not self.config.etapas:
            return False

        eventos = eventos.sort_values("DATA_ATENDIMENTO")
        termos_ancora, _ = self.config.etapas[0]
        ancoras = eventos[
            eventos.apply(
                lambda row: self._match_etapa(
                    row["SERVICO_UPPER"], row["CODIGO_SERVICO"], termos_ancora
                ),
                axis=1,
            )
        ]

        for _, ancora in ancoras.iterrows():
            data_ref = ancora["DATA_ATENDIMENTO"]
            encontrou = True

            for termos_etapa, janela_dias in self.config.etapas[1:]:
                data_limite = data_ref + timedelta(days=janela_dias)
                candidatos = eventos[
                    (eventos["DATA_ATENDIMENTO"] > data_ref)
                    & (eventos["DATA_ATENDIMENTO"] <= data_limite)
                ]
                match = candidatos[
                    candidatos.apply(
                        lambda row: self._match_etapa(
                            row["SERVICO_UPPER"],
                            row["CODIGO_SERVICO"],
                            termos_etapa,
                        ),
                        axis=1,
                    )
                ]
                if match.empty:
                    encontrou = False
                    break
                data_ref = match["DATA_ATENDIMENTO"].min()

            if encontrou:
                return True

        return False

    def detectar_batch(self, timeline: pd.DataFrame) -> pd.Series:
        if timeline.empty:
            return pd.Series(dtype=int, name=self.config.flag_saida)

        resultados = {}
        for uid, grupo in timeline.groupby("ID_USUARIO"):
            resultados[uid] = int(self.detectar_usuario(grupo))
        return pd.Series(resultados, name=self.config.flag_saida, dtype=int)


class PartoTardioDetector:
    IDADE_LIMITE_PRIMEIRO_PARTO = 30
    TERMOS = TERMOS_PARTO

    def __init__(
        self,
        df_usuarios: pd.DataFrame,
        reference_date: Optional[date] = None,
    ) -> None:
        base_date = reference_date or date.today()
        usuarios = df_usuarios.copy()

        id_col = "ID_USUARIO" if "ID_USUARIO" in usuarios.columns else None
        if "IDADE_USU" in usuarios.columns:
            idade_col = "IDADE_USU"
        elif "IDADE" in usuarios.columns:
            idade_col = "IDADE"
        else:
            idade_col = None

        if not id_col or not idade_col:
            self._ano_nascimento: Dict[str, int] = {}
            return

        usuarios = usuarios[[id_col, idade_col]].dropna(subset=[id_col]).drop_duplicates(id_col)
        usuarios = usuarios.rename(columns={id_col: "ID_USUARIO", idade_col: "IDADE_USU"})
        usuarios["ID_USUARIO"] = usuarios["ID_USUARIO"].astype(str).str.strip()
        usuarios["IDADE_USU"] = pd.to_numeric(usuarios["IDADE_USU"], errors="coerce")
        usuarios["ANO_NASC_APROX"] = base_date.year - usuarios["IDADE_USU"]
        self._ano_nascimento = (
            usuarios.dropna(subset=["ANO_NASC_APROX"])
            .set_index("ID_USUARIO")["ANO_NASC_APROX"]
            .astype(int)
            .to_dict()
        )

    def detectar(self, timeline: pd.DataFrame) -> pd.Series:
        if timeline.empty:
            return pd.Series(dtype=int, name=PARTO_TARDIO_CONFIG.flag_saida)

        partos = timeline[
            timeline["SERVICO_UPPER"].apply(
                lambda servico: any(termo in servico for termo in self.TERMOS)
            )
        ].copy()
        if partos.empty:
            return pd.Series(dtype=int, name=PARTO_TARDIO_CONFIG.flag_saida)

        primeiro_parto = (
            partos.sort_values("DATA_ATENDIMENTO")
            .groupby("ID_USUARIO")["DATA_ATENDIMENTO"]
            .first()
        )
        resultados = {}
        for uid, data_parto in primeiro_parto.items():
            ano_nasc = self._ano_nascimento.get(uid)
            resultados[uid] = int(
                ano_nasc is not None
                and (data_parto.year - ano_nasc) > self.IDADE_LIMITE_PRIMEIRO_PARTO
            )
        return pd.Series(resultados, name=PARTO_TARDIO_CONFIG.flag_saida, dtype=int)


class ClinicalChainDetector:
    FLAGS: List[str] = [cadeia.flag_saida for cadeia in CADEIAS_PADRAO] + [
        PARTO_TARDIO_CONFIG.flag_saida
    ]
    PESOS_ESTIMADOS: Dict[str, int] = {
        **{cadeia.flag_saida: cadeia.peso_estimado for cadeia in CADEIAS_PADRAO},
        PARTO_TARDIO_CONFIG.flag_saida: PARTO_TARDIO_CONFIG.peso_estimado,
    }

    def __init__(
        self,
        cadeias: Optional[List[CadeiaConfig]] = None,
        config: Optional[object] = None,
    ) -> None:
        self.cadeias = cadeias or CADEIAS_PADRAO
        self._config = config

    def _todos_usuarios(
        self, timeline: pd.DataFrame, df_usuarios: pd.DataFrame
    ) -> pd.DataFrame:
        ids = set()
        if not timeline.empty:
            ids.update(timeline["ID_USUARIO"].astype(str))
        if "ID_USUARIO" in df_usuarios.columns:
            ids.update(df_usuarios["ID_USUARIO"].dropna().astype(str))
        return pd.DataFrame({"ID_USUARIO": sorted(ids)})

    def detectar(
        self,
        df_producao: pd.DataFrame,
        df_usuarios: pd.DataFrame,
        timeline: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        logger.info("ClinicalChainDetector: construindo timeline...")
        timeline = timeline if timeline is not None else TimelineBuilder(df_producao).build()
        resultado = self._todos_usuarios(timeline, df_usuarios)

        for cadeia in self.cadeias:
            logger.info("Detectando %s", cadeia.flag_saida)
            serie = ChainMatcher(cadeia).detectar_batch(timeline)
            resultado = resultado.merge(
                serie.reset_index().rename(columns={"index": "ID_USUARIO"}),
                on="ID_USUARIO",
                how="left",
            )
            resultado[cadeia.flag_saida] = (
                resultado[cadeia.flag_saida].fillna(0).astype(int)
            )

        serie_parto = PartoTardioDetector(df_usuarios).detectar(timeline)
        resultado = resultado.merge(
            serie_parto.reset_index().rename(columns={"index": "ID_USUARIO"}),
            on="ID_USUARIO",
            how="left",
        )
        resultado[PARTO_TARDIO_CONFIG.flag_saida] = (
            resultado[PARTO_TARDIO_CONFIG.flag_saida].fillna(0).astype(int)
        )

        logger.info("ClinicalChainDetector concluído. Flags geradas: %s", self.FLAGS)
        return resultado

    def resumo(self, df_chains: pd.DataFrame) -> pd.DataFrame:
        rows = []
        if len(df_chains) == 0:
            return pd.DataFrame(
                columns=["FLAG_INFERIDA", "PESO_ESTIMADO", "TOTAL_ATIVO", "PCT_ATIVO"]
            )
        total = len(df_chains)
        for flag in self.FLAGS:
            if flag in df_chains.columns:
                ativos = int(pd.to_numeric(df_chains[flag], errors="coerce").fillna(0).sum())
                rows.append(
                    {
                        "FLAG_INFERIDA": flag,
                        "PESO_ESTIMADO": self.PESOS_ESTIMADOS.get(flag, 0),
                        "TOTAL_ATIVO": ativos,
                        "PCT_ATIVO": round((ativos / total) * 100, 2),
                    }
                )
        if not rows:
            return pd.DataFrame(
                columns=["FLAG_INFERIDA", "PESO_ESTIMADO", "TOTAL_ATIVO", "PCT_ATIVO"]
            )
        return pd.DataFrame(rows).sort_values("TOTAL_ATIVO", ascending=False)

    def yaml_snippet(self) -> str:
        linhas = ["# Pesos das flags inferidas pelo ClinicalChainDetector", "pesos:"]
        for flag, peso in self.PESOS_ESTIMADOS.items():
            linhas.append(f"  {flag}: {peso}")
        return "\n".join(linhas)


FLAGS_NOVAS_PARA_SCORE: List[str] = [
    "MAMOGRAFIA_RESULTADO_INFERIDO_ALTERADO",
    "BRCA_POSITIVO_INFERIDO",
    "CADEIA_INVESTIGACAO_ONCOLOGICA",
    "INVESTIGACAO_POS_BRCA",
    "PARTO_PRIMIPARO_APOS_30",
]
