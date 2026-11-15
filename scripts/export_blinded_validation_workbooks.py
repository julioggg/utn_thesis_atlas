#!/usr/bin/env python3
"""Export REAL 450-thesis blinded human-review Excel packages from private CEDIA data.

Every coder receives an independently ordered workbook plus 450 individual
full-text UTF-8 files. A separate package contains the frozen 80-case section
boundary review. This script DOES NOT create annotations, model predictions,
accuracy estimates or codebook validation. It never changes private source
sheets and never exports thesis-level information to the public repository.

Writes native XLSX OOXML using Python stdlib (no Excel dependency).
Only pyarrow is required to stream the already-frozen source Parquet.

CRITICAL: Packages contain potentially private student research and source
handles. They are unencrypted ZIPs, strictly for authorized institutional
review. DO NOT upload them to public GitHub or email without safeguards.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import re
import tempfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

WORKSPACE = Path(__file__).resolve().parent.parent
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
ODS = (
    ("ODS 1","Fin de la pobreza"),
    ("ODS 2","Hambre cero"),
    ("ODS 3","Salud y bienestar"),
    ("ODS 4","Educación de calidad"),
    ("ODS 5","Igualdad de género"),
    ("ODS 6","Agua limpia y saneamiento"),
    ("ODS 7","Energía asequible y no contaminante"),
    ("ODS 8","Trabajo decente y crecimiento económico"),
    ("ODS 9","Industria, innovación e infraestructura"),
    ("ODS 10","Reducción de las desigualdades"),
    ("ODS 11","Ciudades y comunidades sostenibles"),
    ("ODS 12","Producción y consumo responsables"),
    ("ODS 13","Acción por el clima"),
    ("ODS 14","Vida submarina"),
    ("ODS 15","Vida de ecosistemas terrestres"),
    ("ODS 16","Paz, justicia e instituciones sólidas"),
    ("ODS 17","Alianzas para lograr los objetivos"),
)
PDOT = (
    ("PDOT 1","Sistema Físico Ambiental"),
    ("PDOT 2","Sistema Socio Cultural"),
    ("PDOT 3","Sistema Económico Productivo"),
    ("PDOT 4","Asentamientos Humanos Movilidad Energía Conectividad"),
    ("PDOT 5","Sistema Político Institucional"),
    ("PDOT 6","Ejes Transversales"),
)
ANNOTATION_FIELDS = (
    "study_id","private_source_handle","sdg_primary","sdg_secondary",
    "sdg_no_match","pdot_primary","pdot_secondary","pdot_no_match",
    "uncertain","brief_evidence","coder_notes"
)
BOUNDARY_FIELDS = (
    "review_id","private_source_handle","sampling_stratum",
    "extracted_fulltext_chars","candidate_position_fraction","heading_line",
    "context_before","context_after","trailing_excerpt",
    "human_heading_is_real_references_start","human_corrected_boundary_fraction",
    "human_tail_contains_scientific_contribution",
    "human_trim_from_boundary_safe","human_notes"
)
VALIDATION_STEPS = (
    ("1. Independencia","Cada evaluador utiliza SOLO su paquete A o B. No consulte predicciones E5, otras anotaciones, facultad ni estratos del muestreo."),
    ("2. Documentos completos","Descomprima el ZIP, abra Evidencias/TH-XXXX.txt y estudie objetivos, metodología, resultados y conclusiones. Los extractos de FUENTES solo facilitan navegación."),
    ("3. ODS principal","Seleccione ODS 1 ... ODS 17 en sdg_primary. Justifique una contribución sustantiva, no la mención genérica de palabras."),
    ("4. ODS secundario","Opcional: otro ODS con evidencia directa, diferente de la categoría principal."),
    ("5. PDOT principal","Seleccione PDOT 1 ... PDOT 6 conforme al libro de códigos ANALÍTICO aprobado antes de iniciar. Las etiquetas analíticas NO son equivalentes comprobados de los seis componentes oficiales del PDOT."),
    ("6. PDOT secundario","Opcional; anote un segundo eje con justificación. No repetir la asignación principal."),
    ("7. Ninguna correspondencia","En sdg_no_match / pdot_no_match escriba yes SOLO si ninguna clase tiene evidencia suficiente; en tal caso, deje vacía la primaria y secundaria. En los demás casos escriba no."),
    ("8. Incertidumbre","En uncertain escriba yes si la clasificación o el texto es ambiguo; en los demás casos escriba no."),
    ("9. Evidencia","En brief_evidence explique en 1 a 3 frases evidencia específica de objetivos/resultados para ambos dominios, citando sección o capítulo cuando sea posible."),
    ("10. Observaciones","En coder_notes indique problemas de OCR, fuente incompleta, ambigüedad y decisiones difíciles. No intercambie respuestas entre evaluadores."),
    ("11. Finalización","No cambie study_id ni private_source_handle. Solo complete columnas C:K (amarillas) de ANOTACION. Conserve el libro y las 450 hojas fuente en la carpeta institucional."),
    ("12. Adjudicación","La adjudicación se hará DESPUÉS de congelar ambos libros independientes. Hasta entonces no comparar las respuestas de A y B."),
)
STRUCTURE_STEPS = (
    ("1. Qué se revisa","Para cada tesis, evalúe si el encabezado detectado marca realmente referencias/bibliografía y si la cola puede excluirse sin eliminar contribuciones científicas."),
    ("2. Documento completo","Abra Evidencias/SB-XXXX.txt y examine contexto, índices, secciones finales, anexos, tablas, metodologías y resultados."),
    ("3. Encabezado real","human_heading_is_real_references_start: yes, no o uncertain."),
    ("4. Posición correcta","human_corrected_boundary_fraction: fracción entre 0 y 1 si localiza una frontera mejor. Deje en blanco si no puede verificarla."),
    ("5. Contribución posterior","human_tail_contains_scientific_contribution: yes si contiene resultados, datos o anexos científicos que sería peligroso recortar."),
    ("6. Recorte seguro","human_trim_from_boundary_safe: yes SOLO si el encabezado es real (yes) y la cola no contiene contenido científico (no). Ante duda: uncertain."),
    ("7. Evidencia","Explique dificultades de OCR, otras secciones y dudas en human_notes."),
    ("8. Limitación","La muestra tiene 4 estratos deliberadamente equilibrados (20 por estrato); no estimar prevalencia poblacional sumando 80/80."),
)

def clean_text(value):
    text = "" if value is None else str(value)
    return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\ufffe\uffff]","",text)

def xnode(parent, tag, attrs=None, content=None):
    elem=ET.SubElement(parent,"{"+MAIN+"}"+tag,attrs or {})
    if content is not None:
        elem.text=clean_text(content)
    return elem

def column(index):
    label=""
    while index:
        index, digit=divmod(index-1,26)
        label=chr(65+digit)+label
    return label

def sheet_xml(rows, widths, variant="generic", lists=None):
    """rows are 1-based Excel rows. All cells are literal inline strings."""
    root=ET.Element("{"+MAIN+"}worksheet")
    views=xnode(root,"sheetViews")
    view=xnode(views,"sheetView",{"workbookViewId":"0"})
    xnode(view,"pane",{
        "ySplit":"5","topLeftCell":"A6",
        "activePane":"bottomLeft","state":"frozen"
    })
    xnode(root,"sheetFormatPr",{"defaultRowHeight":"17"})
    cols=xnode(root,"cols")
    for i,w in enumerate(widths,1):
        xnode(cols,"col",{"min":str(i),"max":str(i),
                          "width":str(w),"customWidth":"1"})
    data=xnode(root,"sheetData")
    for rnum,values in enumerate(rows,1):
        rw=xnode(data,"row",{"r":str(rnum),"ht":(
            "29" if rnum==5 else "32" if rnum>=6 else "26"
        ),"customHeight":"1"})
        for cnum,val in enumerate(values,1):
            if val is None or val=="":
                # Emit empty with style if editable, leaving Excel cells ready.
                if rnum>=6 and variant in ("annotation","boundary","consensus"):
                    style = "3" if (
                        (variant=="annotation" and cnum>=3) or
                        (variant=="boundary" and cnum>=10) or
                        (variant=="consensus" and cnum>=19)
                    ) else "2"
                    xnode(rw,"c",{"r":f"{column(cnum)}{rnum}","s":style})
                continue
            style = "4" if rnum==1 else "1" if rnum==5 else "0"
            if rnum>=6 and variant in ("annotation","boundary","consensus"):
                style = "3" if (
                    (variant=="annotation" and cnum>=3) or
                    (variant=="boundary" and cnum>=10) or
                        (variant=="consensus" and cnum>=19)
                ) else "2"
            cell=xnode(rw,"c",{"r":f"{column(cnum)}{rnum}","s":style,
                               "t":"inlineStr"})
            t=xnode(xnode(cell,"is"),"t",{"{http://www.w3.org/XML/1998/namespace}space":"preserve"})
            t.text=clean_text(val)
    if variant in ("annotation","boundary","consensus"):
        last=f"{column(len(widths))}{len(rows)}"
        xnode(root,"autoFilter",{"ref":f"A5:{last}"})
    if lists:
        dvs=xnode(root,"dataValidations",{"count":str(len(lists))})
        for cols_spec,values in lists:
            dv=xnode(dvs,"dataValidation",{
                "type":"list","allowBlank":"1","showInputMessage":"1",
                "sqref":cols_spec
            })
            xnode(dv,"formula1",content='"'+",".join(values)+'"')
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def styles_xml():
    root=ET.Element("{"+MAIN+"}styleSheet")
    fonts=xnode(root,"fonts",{"count":"3"})
    for bold,white in ((False,False),(True,True),(True,False)):
        f=xnode(fonts,"font")
        xnode(f,"sz",{"val":"10"})
        if bold:xnode(f,"b")
        xnode(f,"color",{"rgb":"FFFFFFFF" if white else "FF23354B"})
        xnode(f,"name",{"val":"Aptos"})
    fills=xnode(root,"fills",{"count":"6"})
    for color in (None,None,"FF0E2138","FFDDECF8","FFFFF3CE","FFEAF6F7"):
        pattern=xnode(fills,"fill")
        if color is None:
            xnode(pattern,"patternFill",{"patternType":"none" if len(pattern)==0 else "gray125"})
        else:
            pa=xnode(pattern,"patternFill",{"patternType":"solid"})
            xnode(pa,"fgColor",{"rgb":color})
            xnode(pa,"bgColor",{"indexed":"64"})
    borders=xnode(root,"borders",{"count":"1"})
    bd=xnode(borders,"border")
    for edge in ("left","right","top","bottom","diagonal"):
        xnode(bd,edge)
    cs=xnode(root,"cellStyleXfs",{"count":"1"})
    xnode(cs,"xf",{"numFmtId":"0","fontId":"0","fillId":"0",
                   "borderId":"0"})
    xfs=xnode(root,"cellXfs",{"count":"5"})
    for font,fill in ((0,0),(1,2),(0,3),(0,4),(1,2)):
        xf=xnode(xfs,"xf",{
            "numFmtId":"0","fontId":str(font),"fillId":str(fill),
            "borderId":"0","xfId":"0","applyFill":"1",
            "applyAlignment":"1"
        })
        xnode(xf,"alignment",{"vertical":"center","wrapText":"1"})
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def build_xlsx(target,sheets):
    """sheets: sequence (name, rows, widths, variant, dropdown_rules)."""
    target.parent.mkdir(parents=True,exist_ok=True)
    book=ET.Element("{"+MAIN+"}workbook",{
        "xmlns:r":REL
    })
    sheet_list=xnode(book,"sheets")
    for i,(name,*_) in enumerate(sheets,1):
        xnode(sheet_list,"sheet",{
            "name":name,"sheetId":str(i),
            "{"+REL+"}id":"rId"+str(i)
        })
    xnode(book,"calcPr",{"calcId":"191029","fullCalcOnLoad":"1"})
    types=ET.Element("{"+CT+"}Types")
    ET.SubElement(types,"{"+CT+"}Default",{"Extension":"rels","ContentType":
       "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(types,"{"+CT+"}Default",{"Extension":"xml","ContentType":"application/xml"})
    ET.SubElement(types,"{"+CT+"}Override",{"PartName":"/xl/workbook.xml","ContentType":
       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"})
    ET.SubElement(types,"{"+CT+"}Override",{"PartName":"/xl/styles.xml","ContentType":
       "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"})
    for i in range(1,len(sheets)+1):
        ET.SubElement(types,"{"+CT+"}Override",{"PartName":f"/xl/worksheets/sheet{i}.xml",
          "ContentType":"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
    outer=ET.Element("{"+PKG+"}Relationships")
    ET.SubElement(outer,"{"+PKG+"}Relationship",{
        "Id":"rId1","Type":REL+"/officeDocument","Target":"xl/workbook.xml"
    })
    inner=ET.Element("{"+PKG+"}Relationships")
    for i in range(1,len(sheets)+1):
        ET.SubElement(inner,"{"+PKG+"}Relationship",{
            "Id":"rId"+str(i),"Type":REL+"/worksheet",
            "Target":"worksheets/sheet"+str(i)+".xml"
        })
    ET.SubElement(inner,"{"+PKG+"}Relationship",{
        "Id":"rId"+str(len(sheets)+1),"Type":REL+"/styles",
        "Target":"styles.xml"
    })
    def xml(value):
        return ET.tostring(value,encoding="utf-8",xml_declaration=True)
    with ZipFile(target,"w",compression=ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("[Content_Types].xml",xml(types))
        z.writestr("_rels/.rels",xml(outer))
        z.writestr("xl/workbook.xml",xml(book))
        z.writestr("xl/_rels/workbook.xml.rels",xml(inner))
        z.writestr("xl/styles.xml",styles_xml())
        for i,(_,rows,widths,variant,lists) in enumerate(sheets,1):
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                       sheet_xml(rows,widths,variant,lists))
    return target

def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))

def canonical_handle(row_handle,master_handle):
    if row_handle==master_handle:
        return master_handle
    if row_handle.startswith("'") and row_handle[1:]==master_handle:
        return master_handle
    raise ValueError("Coder worksheet handle mismatched the frozen master")

def load_samples(private):
    master=read_csv(private/"validation/sample_master_private.csv")
    if len(master)!=450:
        raise ValueError("Expected 450 frozen sample cases")
    ids={row["study_id"]:row["handle_id"] for row in master}
    if len(ids)!=450 or len(set(ids.values()))!=450 or "" in ids.values():
        raise ValueError("Frozen study IDs/handles are duplicate or missing")
    coders={}
    for key in ("A","B"):
        src=read_csv(private/f"validation/coder_{key}_private.csv")
        if len(src)!=450 or {x["study_id"] for x in src}!=set(ids):
            raise ValueError("Coder IDs do not match exact frozen 450 cases")
        if any(not set(ANNOTATION_FIELDS).issubset(x) for x in src):
            raise ValueError("Coder worksheets lack expected response fields")
        for row in src:
            row["private_source_handle"]=canonical_handle(
                row["private_source_handle"],ids[row["study_id"]]
            )
        coders[key]=src
    return master,coders

def scan_sources(project,handles,destination):
    import pyarrow.parquet as pq
    source=project/"data/processed/04_clean_corpus.parquet"
    obj=pq.ParquetFile(source)
    names=obj.schema_arrow.names
    if not {"handle_id","full_text"}.issubset(names):
        raise ValueError("Original fulltext parquet lacks handle_id and full_text")
    candidates=("title","titulo","thesis_title","abstract","resumen")
    columns=["handle_id","full_text"]+[x for x in candidates if x in names]
    texts={}
    seen=set()
    for batch in obj.iter_batches(batch_size=16,columns=columns):
        records=batch.to_pylist()
        for row in records:
            handle=str(row.get("handle_id") or "").strip()
            if handle not in handles:continue
            if handle in seen:
                raise ValueError("Duplicate original corpus handle")
            seen.add(handle)
            full=clean_text(row.get("full_text") or "")
            if not full.strip():
                full="[TEXTO EXTRAÍDO VACÍO: consulte el documento institucional original]"
            key=hashlib.sha256(handle.encode("utf-8")).hexdigest()[:24]
            txt=destination/(key+".txt")
            txt.write_text(full,encoding="utf-8")
            title=next((str(row.get(k)) for k in
                ("title","titulo","thesis_title")
                if row.get(k)), "")
            abstract=next((str(row.get(k)) for k in
                ("abstract","resumen")
                if row.get(k)),"")
            texts[handle]={
                "file":txt,"title":clean_text(title),
                "abstract":clean_text(abstract)[:2200],
                "preview":full[:1900],
                "tail":full[-1900:],
                "characters":len(full),
            }
    if set(texts)!=handles:
        raise ValueError(
            "Private sample includes handles missing in original fulltext corpus: "+
            str(len(handles-set(texts)))+" missing; no archive written"
        )
    return texts

def instructions_sheet(steps,title):
    rows=[[title,""]]
    rows.extend([["Atlas UTN · revisión científica ciega · documentos privados",""],
                 ["Solo para revisores institucionales autorizados",""],
                 ["No subir ZIP, XLSX o evidencia a GitHub público",""]])
    rows.append(["PASO","QUÉ DEBE HACER EL EVALUADOR"])
    rows.extend([[a,b] for a,b in steps])
    rows.extend([
        ["REFERENCIA ODS","https://sdgs.un.org/goals"],
        ["PDOT DE IMBABURA","https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027"],
        ["POLÍTICA","Las etiquetas PDOT son analíticas y requieren aprobación previa del libro de códigos. No son una transcripción oficial demostrada."],
    ])
    return ("INSTRUCCIONES",rows,[38,110],"generic",None)

def ods_sheet():
    rows=[["LIBRO DE CÓDIGOS ODS",""],
          ["17 ODS oficiales (los términos de aplicación deben decidirse por evidencia en la tesis)",""],
          ["No copie asignaciones automáticas ni consulte la clasificación histórica.",""],
          ["Fuente: https://sdgs.un.org/goals",""],
          ["Código","Objetivo"]]
    rows.extend(ODS)
    return ("CAT_ODS",rows,[17,68],"generic",None)

def pdot_sheet():
    rows=[["LIBRO DE CÓDIGOS PDOT ANALÍTICO",""],
          ["ESTADO: requiere revisión y congelación del protocolo por el coordinador antes de que los evaluadores codifiquen.",""],
          ["No confundir con los seis componentes oficiales del PDOT 2023–2027.",""],
          ["Fuente institucional: https://www.imbabura.gob.ec/index.php/pdot-aprobado-2023-2027",""],
          ["Código","Etiqueta analítica histórica del atlas"]]
    rows.extend(PDOT)
    return ("CAT_PDOT",rows,[17,75],"generic",None)

def annotation_sheets(cases,texts,label):
    annot=[
        [f"FORMULARIO CIEGO · EVALUADOR {label}"]+[""]*10,
        ["Solo rellene las columnas C–K. Los identificadores y documentos están congelados."]+[""]*10,
        ["Lea INSTRUCCIONES, CAT_ODS, CAT_PDOT antes de iniciar."]+[""]*10,
        ["El listado está intencionalmente ordenado diferente para A y B."]+[""]*10,
        list(ANNOTATION_FIELDS),
    ]
    annot.extend([[row.get(x,"") for x in ANNOTATION_FIELDS] for row in cases])
    cat_ods=",".join([x[0] for x in ODS])
    cat_pdot=",".join([x[0] for x in PDOT])
    validation=[
        ("C6:D455",[x[0] for x in ODS]),
        ("E6:E455",["yes","no"]),
        ("F6:G455",[x[0] for x in PDOT]),
        ("H6:I455",["yes","no"]),
    ]
    source_rows=[
        [f"FUENTES PRIVADAS · EVALUADOR {label}"]+[""]*7,
        ["Los TXT completos se encuentran en Evidencias/ después de EXTRAER el ZIP."]+[""]*7,
        ["Solo se muestran fragmentos orientativos; leer siempre documento íntegro."]+[""]*7,
        ["NO incluye predicciones, márgenes ni facultad del modelo."]+[""]*7,
        ["study_id","private_source_handle","title_if_available",
         "local_fulltext_path","institutional_url_if_available",
         "opening_excerpt","ending_excerpt","fulltext_characters"]
    ]
    for case in cases:
        sid=case["study_id"]
        h=case["private_source_handle"]
        item=texts[h]
        url=h if h.startswith(("http://","https://")) else ""
        source_rows.append([
            sid,h,item["title"],"Evidencias/"+sid+".txt",url,
            item["preview"],item["tail"],str(item["characters"])
        ])
    return [
        ("ANOTACION",annot,[15,40,18,18,18,19,19,19,17,70,60],"annotation",validation),
        ("FUENTES",source_rows,[15,40,45,29,45,78,78,20],"generic",None)
    ]

def boundary_sheets(cases,texts):
    rows=[["AUDITORÍA ESTRUCTURAL · 80 TESIS"]+[""]*13,
          ["Los campos J–N son para el revisor humano."]+[""]*13,
          ["No inferir automáticamente que una sección es segura para recorte."]+[""]*13,
          ["Textos completos disponibles en Evidencias/SB-XXXX.txt."]+[""]*13,
          list(BOUNDARY_FIELDS)]
    rows.extend([[case.get(k,"") for k in BOUNDARY_FIELDS] for case in cases])
    notes=[["FUENTES ESTRUCTURALES PRIVADAS","","",""],
           ["Acceda al TXT completo para verificar cada límite","","",""],
           ["No hay superposición con la muestra ciega de 450","","",""],
           ["Los enlaces de texto son relativos al ZIP extraído","","",""],
           ["review_id","private_source_handle","local_fulltext_path","title_if_available"]]
    for case in cases:
        sid=case["review_id"]
        h=case["private_source_handle"].lstrip("'")
        notes.append([sid,h,"Evidencias/"+sid+".txt",texts[h]["title"]])
    validations=[("J6:J85",["yes","no","uncertain"]),
                 ("L6:M85",["yes","no","uncertain"])]
    return [
        ("REVISION_80",rows,[15,39,35,24,24,40,70,70,70,29,24,29,26,75],
         "boundary",validations),
        ("FUENTES",notes,[15,42,31,58],"generic",None),
    ]

def secure_archive(zip_path, workbook_name, sheets, cases, texts, id_field):
    if zip_path.exists():
        raise FileExistsError(f"Refusing to overwrite private archive: {zip_path}")
    with tempfile.TemporaryDirectory(dir=zip_path.parent) as tmp:
        temp_xlsx=Path(tmp)/workbook_name
        build_xlsx(temp_xlsx,sheets)
        with ZipFile(zip_path,"x",compression=ZIP_DEFLATED,compresslevel=6) as bundle:
            bundle.write(temp_xlsx,workbook_name)
            for case in cases:
                sid=case[id_field]
                h=case["private_source_handle"]
                if h not in texts and h.startswith("'"):
                    h=h[1:]
                if h not in texts:
                    raise ValueError("Private case handle has no corresponding original document")
                bundle.write(texts[h]["file"],"Evidencias/"+sid+".txt")
            bundle.writestr("LEEME_PRIVACIDAD.txt",(
                "Uso exclusivo de evaluadores institucionales autorizados.\n"
                "Este ZIP contiene transcripciones potencialmente sensibles.\n"
                "Descomprímalo antes de usar las rutas indicadas en el Excel.\n"
                "No subir a repositorios públicos ni distribuir sin autorización.\n"
                "No se han incluido predicciones de E5 ni etiquetas del modelo.\n"
            ))
    with ZipFile(zip_path,"r") as z:
        if z.testzip() is not None:
            raise ValueError("ZIP package integrity failed")
        if len(z.namelist()) != len(cases)+2:
            raise ValueError("ZIP expected one fulltext per annotation record")

def run(args):
    ws=WORKSPACE.resolve()
    private_base=(ws/"data").resolve()
    out=args.output_dir.expanduser().resolve()
    if not out.is_relative_to(private_base):
        raise ValueError("Package output must stay in ignored revision/data/")
    private=ws/"data/revision_private"
    master,coders=load_samples(private)
    review_path=private/"section_boundary_review_v1/section_boundary_review_private.csv"
    sections=[]
    if review_path.is_file():
        sections=read_csv(review_path)
        if len(sections)!=80 or len({x["review_id"] for x in sections})!=80:
            raise ValueError("Frozen section-boundary review must contain 80 unique cases")
        masters={x["handle_id"] for x in master}
        handles={x["private_source_handle"].lstrip("'") for x in sections}
        if masters.intersection(handles):
            raise ValueError("Section-boundary records overlap blinded validation sample")
        for x in sections:
            h=x["private_source_handle"]
            if h not in handles and h.startswith("'"):h=h[1:]
            x["private_source_handle"]=h
    wanted=set(x["handle_id"] for x in master)
    wanted.update(x["private_source_handle"] for x in sections)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Private package directory is not empty; never overwrite")
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as stage:
        texts=scan_sources(args.project_root.expanduser().resolve(),wanted,Path(stage))
        for label,cases in coders.items():
            sheets=[instructions_sheet(VALIDATION_STEPS,
                  "GUÍA DE CODIFICACIÓN · EVALUADOR "+label),
                  *annotation_sheets(cases,texts,label),ods_sheet(),pdot_sheet()]
            secure_archive(
                out/f"Evaluador_{label}_450_tesis_PRIVADO.zip",
                f"Evaluador_{label}_450_tesis.xlsx",sheets,cases,texts,"study_id"
            )
        if sections:
            sheets=[
                instructions_sheet(STRUCTURE_STEPS,
                                   "GUÍA DE REVISIÓN ESTRUCTURAL · 80 TESIS"),
                *boundary_sheets(sections,texts)
            ]
            secure_archive(
                out/"Revision_estructural_80_tesis_PRIVADO.zip",
                "Revision_estructural_80_tesis.xlsx",sheets,sections,texts,
                "review_id"
            )
        short=sum(x["characters"]<500 for x in texts.values())
    print("PRIVATE Excel packages generated for coder A and B, 450 theses each.")
    print("Source documents found:",len(texts),
          "| extracted texts shorter than 500 characters:",short)
    print("80-case section package created:",bool(sections))
    print("Output directory (restricted):",out)
    print("No row-level predictions, sample strata for coders, or fulltexts exported to GitHub.")
    print("IMPORTANT: PDOT operational coding definitions still require documentary coordinator approval.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,default=Path(
        "data/revision_private/validation_excel_packages"
    ))
    args=p.parse_args()
    run(args)

if __name__=="__main__":
    main()
