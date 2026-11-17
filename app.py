import time
from fastapi import Header, HTTPException
from pydantic import BaseModel,Field,ConfigDict

from platform_common import application,bounded,operator
from retrieval import Index,grounded_answer

app=application('Financial Document Intelligence','Fictional disclosure search with vector retrieval, metadata filters, reranking and checked quotes.')
index=Index()


class Question(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=3,max_length=500)
    company:str|None=Field(default=None,max_length=80)
    year:int|None=Field(default=None,ge=2000,le=2100)
    k:int=Field(default=4,ge=1,le=6)
    live:bool=False


class Document(BaseModel):
    company:str=Field(min_length=2,max_length=80)
    year:int=Field(ge=2000,le=2100)
    section:str=Field(min_length=2,max_length=100)
    text:str=Field(min_length=20,max_length=20000)


@app.get('/api/catalog')
def catalog():
    return {'companies':sorted({c['company'] for c in index.chunks}),'years':sorted({c['year'] for c in index.chunks}),
            'chunks':len(index.chunks),'embedding':'local TF-IDF lexical vectors, not dense semantic embeddings'}


@app.post('/api/answer')
def answer(body:Question,x_admin_token:str=Header(default='')):
    if body.live:operator(x_admin_token)
    started=time.perf_counter()
    with bounded():
        sources=index.search(body.question,body.company,body.year,body.k)
        try:result=grounded_answer(body.question,sources,body.live)
        except ValueError as error:raise HTTPException(422,str(error)) from None
        except Exception:raise HTTPException(502,'Provider request failed; no extractive fallback was substituted') from None
    return {**result,'sources':sources,'elapsed_ms':round((time.perf_counter()-started)*1000,2),
            'warning':'Quotes are checked for membership, not semantic entailment. Synthetic documents; no investment advice.'}


@app.post('/api/documents',status_code=201)
def add_document(body:Document,x_admin_token:str=Header(default='')):
    operator(x_admin_token)
    with bounded():
        try:document_id=index.add(**body.model_dump())
        except ValueError as error:raise HTTPException(422,str(error)) from None
    return {'document_id':document_id,'status':'indexed'}
