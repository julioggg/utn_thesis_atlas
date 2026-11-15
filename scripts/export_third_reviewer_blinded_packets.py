#!/usr/bin/env python3
"""Generate PRIVATE blinded C-review packets for thematic and structural cases.

Input: frozen CEDIA human response CSVs, already-prepared private human
adjudication queues, and original UTN source full-text parquet.

Output: TWO ZIP archives with source texts and blank decision workbooks:
  Evaluador_C_201_TEMATICAS_CIEGO_PRIVADO.zip  (dynamic case count in workbook)
  Evaluador_C_2_ESTRUCTURA_CIEGO_PRIVADO.zip   (dynamic case count in workbook)

Blinding: evaluator C is NOT shown A/B human labels or notes, disagreement
reasons, thesis sampling strata, or machine predictions. A and B remain
immutable. After C's independent readings are frozen, a separate human
consensus procedure may examine A/B and C. No automated adjudication.

The ZIP files include complete institutional source text; remain strictly
private, authorized access only, never in public GitHub.
"""
from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from export_blinded_validation_workbooks import (
    WORKSPACE, ODS, PDOT, build_xlsx, scan_sources, ods_sheet, pdot_sheet
)
from prepare_thematic_adjudication_queue import select_cases
from prepare_section_boundary_adjudication import make_adjudication_rows

PRIVATE_ROOT = (WORKSPACE / "data/revision_private").resolve()
C_FIELDS = (
    "study_id","private_source_handle","documento_local",
    "sdg_primary","sdg_secondary","sdg_no_match",
    "pdot_primary","pdot_secondary","pdot_no_match",
    "uncertain","brief_evidence","coder_notes","reviewer_identity_date"
)
S_FIELDS = (
    "review_id","private_source_handle","documento_local",
    "candidate_position_fraction","heading_line",
    "context_before","context_after","trailing_excerpt",
    "independent_heading_is_real_references_start",
    "independent_corrected_boundary_fraction",
    "independent_tail_contains_scientific_contribution",
    "independent_trim_from_boundary_safe",
    "independent_notes_and_evidence","reviewer_identity_date",
)


def read_rows(path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def canonical(x):
    return str(x or "").strip().removeprefix("'")


def verify_review_queues():
    """Compare current source CSVs to previously frozen private queues."""
    val=PRIVATE_ROOT/"validation"
    master=read_rows(val/"sample_master_private.csv")
    a=read_rows(val/"coder_A_private.csv")
    b=read_rows(val/"coder_B_private.csv")
    recomputed,_=select_cases(master,a,b)
    queue=read_rows(val/"thematic_adjudication_queue_PRIVATE.csv")
    matched={r["study_id"]:r for r in recomputed}
    submitted={r["study_id"]:r for r in queue}
    if not matched or len(matched)!=len(recomputed) or len(submitted)!=len(queue):
        raise ValueError("Invalid thematic frozen queue roster")
    if matched.keys()!=submitted.keys():
        raise ValueError("The thematic queue does not match current A/B responses")
    for sid in matched:
        expected=matched[sid]
        observed=submitted[sid]
        if canonical(expected["private_source_handle"])!=canonical(
            observed["private_source_handle"]
        ) or expected["reasons_for_review"]!=observed["reasons_for_review"]:
            raise ValueError("The frozen thematic queue does not match current coding")
    structural=read_rows(
        PRIVATE_ROOT/"section_boundary_review_v1/section_boundary_review_private.csv"
    )
    pending,_=make_adjudication_rows(structural)
    frozen=read_rows(
        PRIVATE_ROOT/"section_boundary_review_v1/section_boundary_adjudication_PRIVATE.csv"
    )
    predicted={r["review_id"]:r for r in pending}
    recorded={r["review_id"]:r for r in frozen}
    if len(predicted)!=len(pending) or len(recorded)!=len(frozen):
        raise ValueError("Duplicate structural case ID")
    if predicted.keys()!=recorded.keys():
        raise ValueError("Structural queue differs from source review")
    for key in predicted:
        if canonical(predicted[key]["private_source_handle"])!=canonical(
            recorded[key]["private_source_handle"]
        ):
            raise ValueError("Structural queue source handle mismatch")
    return recomputed,pending


def instruction_sheet(which):
    thematic=which=="thematic"
    if thematic:
        text=[
            ("1. INDEPENDENCIA","Realice la tercera clasificación sin conocer las decisiones de A, B o de E5. No consulte la cola de discrepancias ni la selección de estratos."),
            ("2. FUENTES","Extraiga el ZIP entero, abra Evidencias/TH-XXXX.txt y examine objetivos, metodología, resultados, conclusiones y anexos de cada tesis."),
            ("3. ODS","Seleccione ODS principal y secundario opcional, o registre no correspondencia usando yes y dejando las etiquetas vacías."),
            ("4. PDOT","Seleccione categoría analítica PDOT principal y secundario opcional, exclusivamente bajo un libro de códigos institucional aprobado y congelado."),
            ("5. EVIDENCIA","Justifique cada asignación con hallazgos y sección del documento; no escriba explicaciones genéricas, ni consulte una IA para decidir las categorías."),
            ("6. INCERTIDUMBRE","Escriba yes/no y explique cualquier ausencia de contribución, OCR incompleto o documento que no sea una tesis."),
            ("7. IDENTIDAD","No modifique study_id ni private_source_handle. Complete únicamente D:M, identifique quién revisó y cuándo."),
            ("8. ENTREGA","No consulte las anotaciones A/B hasta que este archivo esté cerrado. Devuelva exclusivamente el Excel completo por canal privado."),
        ]
    else:
        text=[
            ("1. INDEPENDENCIA","Los casos fueron señalados para una segunda comprobación documental. No consulte las respuestas estructurales previas."),
            ("2. FUENTES","Extraiga el ZIP y abra Evidencias/SB-XXXX.txt. Estudie índices, metodología, bibliografía, anexos y todos los fragmentos después del candidato."),
            ("3. ENCABEZADO","En la columna I determine yes/no/uncertain respecto al encabezado detectado por el programa."),
            ("4. CORRECCIÓN","En J registre fracción [0,1] si verifica inicio real distinto; deje vacío cuando no sea posible."),
            ("5. COLA","En K determine si hay contenido científico significativo tras el candidato."),
            ("6. SEGURIDAD","En L escriba yes SOLO si I=yes y K=no. En el resto use no o uncertain, según el documento."),
            ("7. EVIDENCIA","En M detalle evidencia verificable; en N fecha e identidad."),
            ("8. ENTREGA","No cambie columnas A:H, ni intente ajustar la respuesta previa para que un auditor la acepte."),
        ]
    rows=[
        ["CONTROL DE CALIDAD · TERCERA REVISIÓN CIEGA",""],
        ["Privado, solo uso institucional autorizado; NO subir a GitHub",""],
        ["Revisión independiente sin acceso a codificaciones A/B",""],
        ["Las respuestas que completará son decisiones humanas nuevas",""],
        ["PASO","INSTRUCCIÓN"],
    ]
    rows.extend([[x,y] for x,y in text])
    if thematic:
        rows.append(["IMPORTANTE","Las categorías PDOT son analíticas; confirmar el libro de códigos aprobado antes de distribuir."])
    return ("INSTRUCCIONES",rows,[27,120],"generic",None)


def thematic_sheets(cases, source_texts):
    fields=list(C_FIELDS)
    data=[
        ["EVALUADOR C · CLASIFICACIÓN CIEGA"]+[""]*(len(fields)-1),
        ["SIN etiquetas previas A/B, sin predicciones E5, sin motivos de discrepancia"]+[""]*(len(fields)-1),
        ["Complete columnas D:M; después congelaremos sus respuestas"]+[""]*(len(fields)-1),
        ["Si no hay correspondencia, use yes y deje vacías las dos etiquetas"]+[""]*(len(fields)-1),
        fields
    ]
    source=[
        ["FUENTES ORIGINALES PRIVADAS"]+[""]*5,
        ["Los TXT completos están en Evidencias/; descomprima el ZIP"]+[""]*5,
        ["El Excel NO incluye las decisiones A, B ni E5"]+[""]*5,
        ["Use títulos/fragmentos solo para orientación; lea la fuente completa"]+[""]*5,
        ["study_id","private_source_handle","documento_local",
         "title_if_available","opening_excerpt","end_excerpt"]
    ]
    for x in cases:
        sid=x["study_id"]
        handle=canonical(x["private_source_handle"])
        text=source_texts[handle]
        data.append([sid,handle,"Evidencias/"+sid+".txt"]+[""]*10)
        source.append([sid,handle,"Evidencias/"+sid+".txt",
                       text["title"],text["preview"],text["tail"]])
    last=len(data)
    rules=[
        (f"D6:E{last}",[x[0] for x in ODS]),
        (f"F6:F{last}",["yes","no"]),
        (f"G6:H{last}",[x[0] for x in PDOT]),
        (f"I6:J{last}",["yes","no"]),
    ]
    return [
        instruction_sheet("thematic"),
        ("REVISION_C",data,[18,42,30,17,17,17,18,18,17,18,75,60,28],
         "annotation",rules),
        ("FUENTES",source,[16,42,32,55,85,85],"generic",None),
        ods_sheet(),pdot_sheet(),
    ]


def structural_sheets(cases, source_texts):
    fields=list(S_FIELDS)
    data=[
        ["EVALUADOR C · FRONTERAS DE SECCIÓN"]+[""]*(len(fields)-1),
        ["SIN respuestas previas del evaluador estructural"]+[""]*(len(fields)-1),
        ["Complete columnas I:N después de leer cada fuente íntegra"]+[""]*(len(fields)-1),
        ["No aprobar recortes si existe contenido científico posterior"]+[""]*(len(fields)-1),
        fields
    ]
    for x in cases:
        sid=x["review_id"]
        h=canonical(x["private_source_handle"])
        data.append([
            sid,h,"Evidencias/"+sid+".txt",
            x["candidate_position_fraction"],x["heading_line"],
            x["context_before"],x["context_after"],x["trailing_excerpt"],
        ]+[""]*6)
    last=len(data)
    return [
        instruction_sheet("structural"),
        ("REVISION_ESTRUCTURAL_C",data,
         [17,42,30,26,38,85,85,85,27,25,28,28,80,30],
         "annotation",[
             (f"I6:I{last}",["yes","no","uncertain"]),
             (f"K6:L{last}",["yes","no","uncertain"]),
         ]),
    ]


def zip_packet(zip_target, name_xlsx, sheets, cases, texts, identity):
    with tempfile.TemporaryDirectory(dir=zip_target.parent) as stage:
        workbook=Path(stage)/name_xlsx
        build_xlsx(workbook,sheets)
        with ZipFile(zip_target,"x",ZIP_DEFLATED,compresslevel=6) as z:
            z.write(workbook,name_xlsx)
            for item in cases:
                case_id=item[identity]
                handle=canonical(item["private_source_handle"])
                z.write(texts[handle]["file"],f"Evidencias/{case_id}.txt")
            z.writestr("LEEME_PRIVACIDAD.txt",
                       "USO PRIVADO EN CEDIA: datos de tesis originales. No publicar en GitHub.\n"
                       "Excel y TXT deben extraerse juntos antes de la evaluación.\n"
                       "El evaluador C no recibe las respuestas A/B ni predicciones de E5.\n"
                       "Los archivos ZIP no están cifrados: usar transferencia de acceso controlado.\n")
    with ZipFile(zip_target) as archive:
        if archive.testzip() is not None or len(archive.namelist())!=len(cases)+2:
            raise ValueError("Invalid private ZIP packet content")


def run(args):
    output=args.output_dir.expanduser().resolve()
    if not output.is_relative_to(PRIVATE_ROOT):
        raise ValueError("Adjudication packages must remain under private ignored directory")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Output is not empty: never overwrite private adjudication packages")
    thematic,structural=verify_review_queues()
    all_ids=[canonical(item["private_source_handle"]) for item in thematic+structural]
    if len(set(all_ids))!=len(all_ids):
        raise ValueError("Duplicate thesis source across thematic and structural review")
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as td:
        text_data=scan_sources(
            args.project_root.expanduser().resolve(),
            set(all_ids),Path(td)
        )
        if thematic:
            zip_packet(
                output/"Evaluador_C_Tematico_CIEGO_PRIVADO.zip",
                "Evaluador_C_Tematico.xlsx",
                thematic_sheets(thematic,text_data),
                thematic,text_data,"study_id",
            )
        if structural:
            zip_packet(
                output/"Evaluador_C_Estructural_CIEGO_PRIVADO.zip",
                "Evaluador_C_Estructural.xlsx",
                structural_sheets(structural,text_data),
                structural,text_data,"review_id",
            )
    print("Blinded independent third-review private packages created in:",output)
    print("Thematic cases:",len(thematic),
          "| Structural cases:",len(structural))
    print("All case-level documents from verified source:",len(text_data))
    print("No A/B human labels, disagreements, E5 predictions or selection strata exported.")
    print("Do NOT upload these ZIP archives or their Excel workbooks to GitHub.")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",required=True,type=Path)
    p.add_argument("--output-dir",type=Path,default=Path(
        "data/revision_private/adjudication_packages_v1"
    ))
    run(p.parse_args())


if __name__=="__main__":
    main()
