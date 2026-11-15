#!/usr/bin/env python3
"""Build a PRIVATE 450-case expert-consensus workbook from completed A/B and C.

This is a human decision WORKLIST, not an adjudicated gold standard. It
does not change a single source label, document, or model prediction.

- Verifies 120 probability-sampled / 330 targeted cases, but BLINDS their
  per-document strata in the expert-facing workbook.
- Includes all 450 case IDs even if third review C was requested for only 201.
- A/B agreement is presented as an unapproved candidate, NEVER filled into
  any final decision cell.
- Prioritizes A/B main-label conflicts, then C challenging A/B agreement,
  then uncertainty/secondary disagreements.
- Keeps the received third-review provenance unchanged; it does not certify
  C independence. The final cells must be filled/ratified by experts.
- Private XLSX only; do not commit institutional identifiers or text to GitHub.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from audit_uploaded_third_review_proposals import C_FIELDS, read_workbook_rows
from export_blinded_validation_workbooks import (
    WORKSPACE, ODS, PDOT, build_xlsx, ods_sheet, pdot_sheet
)
from prepare_thematic_adjudication_queue import (
    load_csv, canonical, select_cases
)
from reviewer_three_coder_comparison import comparison, label

PRIVATE=(WORKSPACE/"data/revision_private").resolve()
FIELDS=(
    "study_id","private_source_handle",
    "review_priority","review_reason",
    "A_ODS_primary","B_ODS_primary","C_ODS_primary",
    "A_PDOT_primary","B_PDOT_primary","C_PDOT_primary",
    "A_B_ODS_unapproved_candidate","A_B_PDOT_unapproved_candidate",
    "A_uncertain","B_uncertain","C_uncertain",
    "A_evidence","B_evidence","C_evidence",
    "final_sdg_primary","final_sdg_no_match",
    "final_pdot_primary","final_pdot_no_match",
    "final_expert_rationale","final_expert_name_and_date",
)
EDITABLE=FIELDS[18:]

def proposal(a,b,dom):
    x=label(a,dom)
    y=label(b,dom)
    return x if x==y else ""

def prioritize(a,b,c,queue_entry):
    conflict=any(label(a,k)!=label(b,k) for k in ("sdg","pdot"))
    dissent=bool(c and any(
        label(a,k)==label(b,k) and label(c,k)!=label(a,k)
        for k in ("sdg","pdot")
    ))
    if conflict:return "P0_AB_PRIMARY_CONFLICT"
    if dissent:return "P1_C_CHALLENGES_AB"
    if c:return "P2_SECONDARY_OR_UNCERTAINTY"
    return "P3_AB_UNCONTESTED"

def generate(master,a,b,c,queue):
    comparison(master,a,b,c,queue)  # strict 450/120/330 and handle checks
    by_a={r["study_id"]:r for r in a}
    by_b={r["study_id"]:r for r in b}
    by_c={r["study_id"]:r for r in c}
    by_queue={r["study_id"]:r for r in queue}
    records=[]
    for original in master:
        sid=original["study_id"]
        aa,bb=by_a[sid],by_b[sid]
        cc=by_c.get(sid)
        status=prioritize(aa,bb,cc,by_queue.get(sid))
        reasons=by_queue[sid]["reasons_for_review"] if sid in by_queue else ""
        item={
            "study_id":sid,
            "private_source_handle":canonical(original["handle_id"]),
            "review_priority":status,
            "review_reason":reasons,
            "A_ODS_primary":label(aa,"sdg"),
            "B_ODS_primary":label(bb,"sdg"),
            "C_ODS_primary":label(cc,"sdg") if cc else "",
            "A_PDOT_primary":label(aa,"pdot"),
            "B_PDOT_primary":label(bb,"pdot"),
            "C_PDOT_primary":label(cc,"pdot") if cc else "",
            "A_B_ODS_unapproved_candidate":proposal(aa,bb,"sdg"),
            "A_B_PDOT_unapproved_candidate":proposal(aa,bb,"pdot"),
            "A_uncertain":aa.get("uncertain",""),
            "B_uncertain":bb.get("uncertain",""),
            "C_uncertain":cc.get("uncertain","") if cc else "",
            "A_evidence":aa.get("brief_evidence",""),
            "B_evidence":bb.get("brief_evidence",""),
            "C_evidence":cc.get("brief_evidence","") if cc else "",
        }
        item.update({key:"" for key in EDITABLE})
        records.append(item)
    if len(records)!=450 or len({r["study_id"] for r in records})!=450:
        raise ValueError("Cannot produce complete 450-case worklist")
    return sorted(records,key=lambda r:(r["review_priority"],r["study_id"]))

def instructions():
    content=[
        ["PROTOCOLO DE CONSENSO · 450 TESIS",""],
        ["Solo para el comité de adjudicación autorizado; contenido privado de CEDIA",""],
        ["NO es una hoja de referencia definitiva ni prueba de precisión E5",""],
        ["Los candidatos A/B en L/M requieren aprobación, NO se aceptan automáticamente",""],
        ["PASO","INDICACIÓN"],
        ["1. CONGELAR","Conservar A, B y C como originales. No borrar declaraciones de uso de IA ni notas."],
        ["2. PRIORIDAD P0","Resolver discrepancias sobre ODS/PDOT PRINCIPAL mediante evidencia de tesis completas."],
        ["3. PRIORIDAD P1","Revisar casos donde A/B coinciden pero C asigna una categoría distinta."],
        ["4. PRIORIDAD P2","Revisar incertidumbre, etiquetas secundarias distintas o ausencia de correspondencia."],
        ["5. PRIORIDAD P3","Los casos A=B sin bandera pueden ratificarse mediante procedimiento documentado y autorización explícita del comité; no asumir certeza automática."],
        ["6. ODS","Solo ODS 1..17; si no corresponde, dejar principal vacío y escribir yes en no_match."],
        ["7. PDOT","Solo PDOT 1..6 bajo libro de códigos analítico aprobado; si no corresponde, dejar principal vacío y marcar yes."],
        ["8. EVIDENCIA","Registrar fundamento real en tesis, sección, discrepancias y resolución."],
        ["9. REVISOR","Registrar nombre/fecha de quienes aprueban la decisión humana final."],
        ["10. RESPUESTAS","Completar columnas S:X únicamente; no modificar las columnas A:R de origen."],
        ["11. POBLACIÓN","Los 120 aleatorios y 330 enriquecidos NO se mezclan al estimar rendimiento poblacional."],
        ["12. ORIGEN C","C presenta una declaración de autoría humana posterior y marcas IA en el XLSX: conservar y documentar ambos hechos."],
        ["13. PROTECCIÓN","Nunca publicar los identificadores, justificaciones o textos de tesis en GitHub."],
    ]
    return ("INSTRUCCIONES",content,[28,116],"generic",None)

def create_workbook(rows,output):
    intro=[
        ["CONSENSO HUMANO · 450 CASOS"]+[""]*(len(FIELDS)-1),
        ["Las respuestas de A/B/C son contexto; NO son una votación automática"]+[""]*(len(FIELDS)-1),
        ["Columnas S:X amarillas destinadas al experto adjudicador"]+[""]*(len(FIELDS)-1),
        ["No convertir candidatos L:M en ground truth sin acta de aprobación"]+[""]*(len(FIELDS)-1),
        list(FIELDS),
    ]
    intro.extend([[row[field] for field in FIELDS] for row in rows])
    end=len(intro)
    lists=[
        (f"S6:S{end}",[key for key,_ in ODS]),
        (f"T6:T{end}",["yes","no"]),
        (f"U6:U{end}",[key for key,_ in PDOT]),
        (f"V6:V{end}",["yes","no"]),
    ]
    tall=[16,38,30,40,17,17,17,19,19,19,22,22,15,15,15,74,74,74,18,18,18,18,85,35]
    summary=Counter(r["review_priority"] for r in rows)
    blocks=[
        ["RESUMEN DE TRABAJO DE CONSENSO",""],
        ["No es gold standard; decisiones finales vacías",""],
        ["No se calculan precisión, F1 o kappa frente a E5",""],
        ["Las seis categorías PDOT son analíticas, no una equivalencia oficial verificada",""],
        ["CATEGORÍA DE TRABAJO","NÚMERO DE TESIS"],
    ]
    blocks.extend([[key,str(summary[key])] for key in sorted(summary)])
    blocks.append(["TOTAL",str(len(rows))])
    build_xlsx(output,[
        instructions(),
        ("ADJUDICACION_450",intro,tall,"consensus",lists),
        ("CONTROL",blocks,[40,24],"generic",None),
        ods_sheet(),pdot_sheet(),
    ])
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--c-workbook",type=Path,default=Path(
        "data/revision_private/Evaluador_C_Tematico_COMPLETADO_PROPUESTA.xlsx"
    ))
    p.add_argument("--output",type=Path,default=Path(
        "data/revision_private/validation/"
        "CONSENSO_450_PARA_REVISION_EXPERTA_PRIVADO.xlsx"
    ))
    a=p.parse_args()
    output=a.output.expanduser().resolve()
    workbook=a.c_workbook.expanduser().resolve()
    if not output.is_relative_to(PRIVATE) or not workbook.is_relative_to(PRIVATE):
        raise ValueError("All case-level source and workbook files must stay private")
    if output.exists():
        raise FileExistsError("Never overwrite a previous expert consensus workbook")
    d=PRIVATE/"validation"
    master=load_csv(d/"sample_master_private.csv")
    A=load_csv(d/"coder_A_private.csv")
    B=load_csv(d/"coder_B_private.csv")
    queue=load_csv(d/"thematic_adjudication_queue_PRIVATE.csv")
    C=read_workbook_rows(workbook,C_FIELDS)
    rows=generate(master,A,B,C,queue)
    summary=create_workbook(rows,output)
    print("PRIVATE 450-case expert consensus WORKLIST:",output)
    print("Priorities:",dict(summary))
    print("Human final columns are ALL BLANK. No machine metrics computed.")
    print("Requires explicit expert sign-off and PDOT codebook approval before gold standard.")

if __name__=="__main__":
    main()
