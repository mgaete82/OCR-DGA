# -*- coding: utf-8 -*-

import re
import unicodedata
import pandas as pd
import pytesseract
import pymupdf as fitz

from pathlib import Path
from PIL import Image


# ==========================================================
# CONFIGURACION
# ==========================================================

PDF_DIR = Path("PDF")
TXT_DIR = Path("texto")
SALIDA_DIR = Path("salida")
LOG_DIR = Path("logs")

TXT_DIR.mkdir(exist_ok=True)
SALIDA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

TESSERACT_PATH = (
    r"C:\Users\marco.gaete\AppData\Local\Tesseract-OCR\tesseract.exe"
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

OCR_LANG = "spa"

METADATA_CSV = SALIDA_DIR / "metadata.csv"
CALIDAD_CSV = SALIDA_DIR / "calidad_ocr.csv"
CLASIFICACION_CSV = SALIDA_DIR / "clasificacion_documental.csv"
FALTANTES_CSV = SALIDA_DIR / "expedientes_no_detectados.csv"
ERRORES_CSV = SALIDA_DIR / "errores.csv"
VALIDACION_V4_CSV = SALIDA_DIR / "validacion_v4.csv"


# ==========================================================
# EXPEDIENTES FALLIDOS V3
# ==========================================================

FALLIDOS_V3 = {
    "Expedientes_P0001_00022.pdf",
    "Expedientes_P0001_00079.pdf",
    "Expedientes_P0001_00082.pdf",
    "Expedientes_P0001_00084.pdf",
    "Expedientes_P0001_00085.pdf",
    "Expedientes_P0001_00091.pdf",
    "Expedientes_P0001_00092.pdf",
    "Expedientes_P0001_00093.pdf",
    "Expedientes_P0001_00094.pdf",
    "Expedientes_P0001_00095.pdf",
    "Expedientes_P0001_00097.pdf",
    "Expedientes_P0001_00098.pdf",
    "Expedientes_P0001_00099.pdf",
}


# ==========================================================
# TIPOS OFICIALES DGA
# ==========================================================

TIPOS_EXPEDIENTE = [
    "A",
    "AC",
    "C",
    "D",
    "DIA",
    "E",
    "F",
    "H",
    "M",
    "ND",
    "NE",
    "NR",
    "O",
    "OI",
    "P",
    "PT",
    "R",
    "S",
    "UA",
    "V",
    "VAR",
    "VC",
    "VD",
    "VF",
    "VP",
    "VPC",
    "VR",
    "VS",
    "VT",
    "VV",
]

TIPOS_REGEX = "|".join(
    sorted(
        TIPOS_EXPEDIENTE,
        key=len,
        reverse=True
    )
)


# ==========================================================
# PALABRAS CLAVE DE CONTEXTO
# ==========================================================

CLAVES_CONTEXTO = [
    "EXPEDIENTE",
    "EXP.",
    "ROL",
    "REFERENCIA",
    "REF.",
    "ANT.",
    "ANTECEDENTE",
    "SOLICITUD",
    "INGRESO",
    "MATERIA",
    "INC.",
    "MAT.",
]


# ==========================================================
# PATRONES V4.1
# ==========================================================

PATRON_EXPEDIENTE_MODERNO = re.compile(
    rf"""
    \b
    ({TIPOS_REGEX})
    [\s\-_:=/]*
    \d+
    (?:
        [\s\-_:=/]*
        \d+
    ){{0,3}}
    \b
    """,
    re.IGNORECASE | re.VERBOSE
)

# Patrón robustecido para expedientes históricos DGA con estructura [PREFIJO]-[ROMANO]-[CORRELATIVO]
PATRON_EXPEDIENTE_HISTORICO = re.compile(
    rf"""
    \b
    ({TIPOS_REGEX})
    [\s\-_:=/]*
    ([IVXLCDM]+)
    [\s\-_:=/]*
    (\d+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE
)

PATRON_ROL = re.compile(
    r"""
    ROL
    \s*
    (?:NRO|NR|N°|Nº)?
    \s*
    [:=\- ]*
    \s*
    (
        [A-Z0-9\-]+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ==========================================================
# CORRECCIONES UTF8
# ==========================================================

CORRECCIONES_CODIFICACION = {
    "SEÃ‘OR": "SEÑOR",
    "REGIÃ“N": "REGIÓN",
    "CAPTACIÃ“N": "CAPTACIÓN",
    "OPOSICIÃ“N": "OPOSICIÓN",
    "PÃšBLICAS": "PÚBLICAS",
    "LOCALIZACIÃ“N": "LOCALIZACIÓN",
    "UTILIZACIÃ“N": "UTILIZACIÓN",
    "RESOLUCIÃ“N": "RESOLUCIÓN",
    "INSCRIPCIÃ“N": "INSCRIPCIÓN",
    "CONCESIÃ“N": "CONCESIÓN",
    "DIRECCIÃ“N": "DIRECCIÓN",
    "POSESIÃ“N": "POSESIÓN",
}


# ==========================================================
# CORRECCIONES OCR
# ==========================================================

CORRECCIONES_OCR = {
    "XIT": "XII",
    "XI1": "XII",
    "XI|": "XII",
    "EXPEDLENTE": "EXPEDIENTE",
    "EXPEDIEMTE": "EXPEDIENTE",
    "EXPEDIEHTE": "EXPEDIENTE",
    "EXPEOIENTE": "EXPEDIENTE",
    "NR =": "NR ",
    "NR=": "NR ",
    "=7": "-7",
    "=8": "-8",
    "=9": "-9",
    "VV ": "VV-",
    "VV.": "VV-",
    "ND ": "ND-",
    "ND.": "ND-",
    "VP ": "VP-",
    "VP.": "VP-",
    "VF ": "VF-",
    "VF.": "VF-",
    "VT ": "VT-",
    "VT.": "VT-",
}


# ==========================================================
# NORMALIZACION UTF8
# ==========================================================

def corregir_codificacion(texto):

    try:
        nuevo = texto.encode("latin1").decode("utf-8")
        texto = nuevo
    except Exception:
        pass

    for origen, destino in CORRECCIONES_CODIFICACION.items():
        texto = texto.replace(origen, destino)

    return texto


# ==========================================================
# NORMALIZACION GENERAL
# ==========================================================

def normalizar_texto(texto):

    texto = corregir_codificacion(texto)

    texto = texto.upper()

    for origen, destino in CORRECCIONES_OCR.items():
        texto = texto.replace(origen, destino)

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    return texto


# ==========================================================
# EXTRAER TEXTO NATIVO
# ==========================================================

def extraer_texto_nativo(pdf_path):

    texto = ""

    try:

        doc = fitz.open(pdf_path)

        for pagina in doc:
            texto += pagina.get_text()

        doc.close()

    except Exception:
        pass

    return texto


# ==========================================================
# OCR
# ==========================================================

def ocr_pdf(pdf_path):

    texto = ""

    doc = fitz.open(pdf_path)

    total = doc.page_count

    for pagina_numero in range(total):

        pagina = doc[pagina_numero]

        pix = pagina.get_pixmap(
            matrix=fitz.Matrix(3, 3),
            alpha=False
        )

        temporal = (
            TXT_DIR /
            f"_tmp_{pdf_path.stem}_{pagina_numero}.png"
        )

        pix.save(str(temporal))

        try:

            imagen = Image.open(temporal)

            pagina_texto = (
                pytesseract.image_to_string(
                    imagen,
                    lang=OCR_LANG
                )
            )

            texto += pagina_texto + "\n"

        except Exception:
            pass

        try:
            temporal.unlink(missing_ok=True)
        except Exception:
            pass

    doc.close()

    return texto


# ==========================================================
# BUSQUEDA CONTEXTUAL
# ==========================================================

def extraer_contextos(texto):

    contextos = []

    for clave in CLAVES_CONTEXTO:

        inicio = 0

        while True:

            pos = texto.find(clave, inicio)

            if pos < 0:
                break

            desde = max(0, pos - 120)
            hasta = min(len(texto), pos + 250)

            contextos.append(
                texto[desde:hasta]
            )

            inicio = pos + 1

    if not contextos:
        contextos.append(texto)

    return contextos


# ==========================================================
# DETECCION DE EXPEDIENTE V4.1
# ==========================================================

def detectar_expediente(texto):

    contextos = extraer_contextos(texto)

    # --------------------------------------
    # 1. BUSCAR EN CONTEXTOS RELEVANTES (MODERNOS)
    # --------------------------------------

    for contexto in contextos:

        m = PATRON_EXPEDIENTE_MODERNO.search(contexto)

        if m:

            expediente = m.group(0)

            # Evitar que números romanos sean parcialmente consumidos como modernos si hay patrón histórico
            if any(f"-{r}-" in f"-{expediente}-" for r in ["III", "XII", "IV", "VI", "IX"]):
                continue

            expediente = re.sub(r"[\s_/]+", "-", expediente)
            expediente = re.sub(r"-+", "-", expediente)
            expediente = expediente.strip("-")

            return (
                expediente,
                "EXPEDIENTE_MODERNO"
            )

    # --------------------------------------
    # 2. BUSCAR EN CONTEXTOS RELEVANTES (HISTORICOS DGA)
    # --------------------------------------

    for contexto in contextos:

        m = PATRON_EXPEDIENTE_HISTORICO.search(contexto)

        if m:
            prefijo = m.group(1).upper()
            romano = m.group(2).upper()
            correlativo = m.group(3)

            # Normalización del correlativo histórico para mantener consistencia (ej: M-XII-027)
            if len(correlativo) < 3 and int(correlativo) >= 10:
                correlativo = correlativo.zfill(3)

            expediente = f"{prefijo}-{romano}-{correlativo}"
            
            return (
                expediente,
                "EXPEDIENTE_HISTORICO"
            )

    # --------------------------------------
    # 3. ROL
    # --------------------------------------

    for contexto in contextos:

        m = PATRON_ROL.search(
            contexto
        )

        if m:

            expediente = (
                m.group(1)
                .strip()
            )

            return (
                expediente,
                "ROL"
            )

    # --------------------------------------
    # 4. BUSQUEDA GLOBAL (MODERNO)
    # --------------------------------------

    m = PATRON_EXPEDIENTE_MODERNO.search(
        texto
    )

    if m:

        expediente = m.group(0)
        
        if not any(f"-{r}-" in f"-{expediente}-" for r in ["III", "XII", "IV", "VI", "IX"]):
            expediente = re.sub(r"[\s_/]+", "-", expediente)
            expediente = re.sub(r"-+", "-", expediente)
            expediente = expediente.strip("-")

            return (
                expediente,
                "BUSQUEDA_GLOBAL_MODERNO"
            )

    # --------------------------------------
    # 5. BUSQUEDA GLOBAL (HISTORICO DGA - Requerimiento v4.1)
    # --------------------------------------

    m = PATRON_EXPEDIENTE_HISTORICO.search(texto)

    if m:
        prefijo = m.group(1).upper()
        romano = m.group(2).upper()
        correlativo = m.group(3)

        if len(correlativo) < 3 and int(correlativo) >= 10:
            correlativo = correlativo.zfill(3)

        expediente = f"{prefijo}-{romano}-{correlativo}"

        return (
            expediente,
            "BUSQUEDA_GLOBAL_HISTORICO"
        )

    return "", ""


# ==========================================================
# CLASIFICACION DOCUMENTAL V4
# ==========================================================

def clasificar_documento(texto):

    texto = texto.upper()

    if (
        "SALUDA ATENTAMENTE" in texto
        or "OFICIO" in texto
        or "DISTRIBUCION" in texto
    ):
        return "OFICIO"

    if (
        "RESUELVO" in texto
        or "RESOLUCION" in texto
        or "ARTICULO 1" in texto
        or "ARTICULO PRIMERO" in texto
    ):
        return "RESOLUCION"

    if (
        "OPOSICION" in texto
        and "SOLICITUD" in texto
    ):
        return "OPOSICION"

    if (
        "FISCALIZACION" in texto
        or "ACTA DE INSPECCION" in texto
    ):
        return "FISCALIZACION"

    if (
        "DENUNCIA" in texto
    ):
        return "DENUNCIA"

    if (
        "INFORME TECNICO" in texto
        or "MEMORIA TECNICA" in texto
    ):
        return "INFORME_TECNICO"

    if (
        "PLANO DE UBICACION" in texto
        or "PLANO N" in texto
        or "CROQUIS" in texto
    ):
        return "PLANO"

    if (
        "VISTOS" in texto
        and "CONSIDERANDO" in texto
    ):
        return "ACTO_ADMINISTRATIVO"

    if (
        "DERECHO DE APROVECHAMIENTO"
        in texto
    ):
        return "DERECHO_APROVECHAMIENTO"

    return "EXPEDIENTE_ADMINISTRATIVO"


# ==========================================================
# EXTRACCION DE CAMPOS
# ==========================================================

def extraer_fecha(texto):

    patrones = [

        r"\d{2}/\d{2}/\d{2,4}",

        r"\d{1,2}\s+DE\s+[A-Z]+\s+DE\s+\d{4}",

    ]

    for patron in patrones:

        m = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if m:
            return m.group(0)

    return ""


def extraer_comuna(texto):

    m = re.search(
        r"COMUNA\s*[:\-]?\s*([A-Z ]{3,60})",
        texto
    )

    if m:

        return (
            m.group(1)
            .strip()
        )

    return ""


def extraer_plano(texto):

    m = re.search(
        r"PLANO\s*N[°º]?\s*(\d+)",
        texto
    )

    if m:
        return m.group(1)

    return ""


# ==========================================================
# REANUDACION
# ==========================================================

def obtener_archivos_ya_procesados():

    if not METADATA_CSV.exists():
        return set()

    try:

        df = pd.read_csv(
            METADATA_CSV,
            dtype=str
        )

        return set(
            df["archivo"]
            .astype(str)
            .tolist()
        )

    except Exception:

        return set()


# ==========================================================
# PROCESAR PDF
# ==========================================================

def procesar_pdf(pdf_path):

    resultado = {

        "archivo": pdf_path.name,

        "tipo_documento": "",

        "expediente": "",

        "patron_detectado": "",

        "paginas": 0,

        "ocr_aplicado": False,

        "texto_extraido": False,

        "largo_texto": 0,

        "fecha_detectada": "",

        "comuna": "",

        "plano": "",

        "error": "",
    }

    try:

        doc = fitz.open(pdf_path)

        resultado["paginas"] = (
            doc.page_count
        )

        doc.close()

        texto_nativo = (
            extraer_texto_nativo(
                pdf_path
            )
        )

        texto = texto_nativo

        if len(texto.strip()) < 100:

            texto_ocr = ocr_pdf(
                pdf_path
            )

            texto += "\n" + texto_ocr

            resultado[
                "ocr_aplicado"
            ] = True

        texto = normalizar_texto(
            texto
        )

        expediente, patron = (
            detectar_expediente(
                texto
            )
        )

        resultado[
            "tipo_documento"
        ] = clasificar_documento(
            texto
        )

        resultado[
            "expediente"
        ] = expediente

        resultado[
            "patron_detectado"
        ] = patron

        resultado[
            "fecha_detectada"
        ] = extraer_fecha(
            texto
        )

        resultado[
            "comuna"
        ] = extraer_comuna(
            texto
        )

        resultado[
            "plano"
        ] = extraer_plano(
            texto
        )

        resultado[
            "texto_extraido"
        ] = len(
            texto.strip()
        ) > 0

        resultado[
            "largo_texto"
        ] = len(texto)

        txt_file = (
            TXT_DIR /
            f"{pdf_path.stem}.txt"
        )

        txt_file.write_text(
            texto,
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as e:

        resultado["error"] = str(e)

    return resultado


# ==========================================================
# VALIDACION V4
# ==========================================================

def generar_validacion_v4(df):

    registros = []

    for archivo in FALLIDOS_V3:

        fila = df[
            df["archivo"] == archivo
        ]

        if fila.empty:

            registros.append({
                "archivo": archivo,
                "expediente_v4": "",
                "tipo_documento": "",
                "recuperado_v4": "NO"
            })

            continue

        expediente = str(
            fila.iloc[0]["expediente"]
        ).strip()

        registros.append({

            "archivo": archivo,

            "expediente_v4": expediente,

            "tipo_documento":
            fila.iloc[0][
                "tipo_documento"
            ],

            "recuperado_v4":
            "SI"
            if expediente
            else "NO"
        })

    df_validacion = pd.DataFrame(
        registros
    )

    df_validacion.to_csv(
        VALIDACION_V4_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    return df_validacion


# ==========================================================
# MAIN
# ==========================================================

def main():

    pdfs = sorted(
        PDF_DIR.glob("*.pdf")
    )

    print()
    print("=" * 60)
    print("OCR DOCUMENTAL V4.1 (PRODUCCIÓN HISTÓRICOS)")
    print("=" * 60)

    print(
        f"PDF encontrados : {len(pdfs)}"
    )

    resultados = []

    for i, pdf in enumerate(
        pdfs,
        start=1
    ):

        print(
            f"[{i}/{len(pdfs)}] "
            f"{pdf.name}"
        )

        resultado = procesar_pdf(
            pdf
        )

        resultados.append(
            resultado
        )

    df = pd.DataFrame(
        resultados
    )

    df.to_csv(
        METADATA_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    df[
        [
            "archivo",
            "paginas",
            "ocr_aplicado",
            "texto_extraido",
            "largo_texto",
            "expediente"
        ]
    ].to_csv(
        CALIDAD_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    df[
        [
            "archivo",
            "tipo_documento",
            "expediente",
            "patron_detectado"
        ]
    ].to_csv(
        CLASIFICACION_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    df[
        df["expediente"]
        .fillna("")
        .astype(str)
        .str.strip()
        == ""
    ][
        [
            "archivo",
            "tipo_documento"
        ]
    ].to_csv(
        FALTANTES_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    df[
        df["error"]
        .fillna("")
        .astype(str)
        .str.strip()
        != ""
    ][
        [
            "archivo",
            "error"
        ]
    ].to_csv(
        ERRORES_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    validacion = (
        generar_validacion_v4(df)
    )

    total = len(df)

    detectados = (
        df["expediente"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )

    porcentaje = (
        detectados / total * 100
        if total
        else 0
    )

    recuperados = (
        validacion[
            validacion[
                "recuperado_v4"
            ] == "SI"
        ].shape[0]
    )

    print()
    print("=" * 60)
    print("RESUMEN V4.1")
    print("=" * 60)

    print(
        f"PDFs procesados      : {total}"
    )

    print(
        f"Expedientes hallados : {detectados}"
    )

    print(
        f"Porcentaje exito     : "
        f"{porcentaje:.2f}%"
    )

    print()

    print(
        f"Fallidos V3          : "
        f"{len(FALLIDOS_V3)}"
    )

    print(
        f"Recuperados por V4.1 : "
        f"{recuperados}"
    )

    print()

    print(METADATA_CSV)
    print(CALIDAD_CSV)
    print(CLASIFICACION_CSV)
    print(FALTANTES_CSV)
    print(ERRORES_CSV)
    print(VALIDACION_V4_CSV)


if __name__ == "__main__":
    main()
