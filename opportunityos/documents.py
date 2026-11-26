"""Read the user's master CV locally; never invent or auto-verify profile facts."""
import io,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree

def catalog(store):
    with store.db() as db:return [dict(r) for r in db.execute('SELECT * FROM documents ORDER BY added DESC')]

def master_cv(store):
    docs=catalog(store);chosen=store.settings().get('master_cv_id')
    candidates=[d for d in docs if d['id']==chosen] if chosen else [d for d in docs if re.search(r'\b(cv|resume|résumé)\b',d['name'],re.I)]
    if not chosen and not candidates and len(docs)==1:candidates=docs
    if not candidates:return None
    doc=candidates[0]
    if re.search(r'passport|identity|transcript|medical|bank',doc['name'],re.I):return None
    return doc

def document_bytes(store,ident):
    doc=next((d for d in catalog(store) if d['id']==ident),None)
    if not doc:raise ValueError('Document not found')
    data=(store.directory/'documents'/doc['id']).read_bytes()
    if len(data)>10_000_000:raise ValueError('Document exceeds size limit')
    return doc,data

def read_text(store,ident):
    doc,data=document_bytes(store,ident);suffix=Path(doc['name']).suffix.lower()
    if suffix=='.txt':text=data.decode('utf-8',errors='replace')
    elif suffix=='.pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('Install requirements-documents.txt to read PDF CVs') from None
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted:raise ValueError('Unlock this PDF before importing it')
        if len(reader.pages)>30:raise ValueError('Choose a CV of 30 pages or fewer')
        text='\n'.join(page.extract_text() or '' for page in reader.pages)
    elif suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entry=archive.getinfo('word/document.xml')
            if entry.file_size>5_000_000:raise ValueError('Document text exceeds size limit')
            root=ElementTree.fromstring(archive.read(entry))
            text='\n'.join(''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
    else:raise ValueError('Choose a PDF, DOCX or text CV')
    text=text.strip()[:24000]
    if len(text)<40:raise ValueError('No readable CV text. Scanned PDFs need a text-readable version.')
    return doc,text

def context(store):
    facts={key:row['value'] for key,row in store.facts().items() if row['verified'] and row['share'] and row['value']}
    cv=master_cv(store);documents=[];warnings=[]
    if cv:
        try:
            doc,text=read_text(store,cv['id'])
            documents=[{'id':doc['id'],'name':doc['name'],'text':text,'source_id':'document:'+doc['id']}]
        except ValueError as error:warnings.append(str(error))
    else:warnings.append('No master CV selected')
    return {'facts':facts,'documents':documents,'warnings':warnings}
