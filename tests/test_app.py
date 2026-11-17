import os
import tempfile
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='rag-test-')
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app,index
from retrieval import grounded_answer


class RagTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)
    def test_metadata_filter_prevents_company_leakage(self):
        data=self.client.post('/api/answer',json={'question':'2025 revenue','company':'Cedar','year':2025}).json()
        self.assertTrue(data['sources'])
        self.assertTrue(all(s['company']=='Cedar' and s['year']==2025 for s in data['sources']))
    def test_empty_retrieval_abstains(self):
        self.assertEqual(index.search('zqxvnj'),[])
        self.assertEqual(grounded_answer('unknown',[])['mode'],'abstained')
    def test_exact_quote_in_extractive_result(self):
        data=self.client.post('/api/answer',json={'question':'operating cash flow','company':'Northstar','year':2025}).json()
        self.assertTrue(any('24 million' in c['quote'] for c in data['claims']))
    def test_live_operator_required(self):
        self.assertEqual(self.client.post('/api/answer',json={'question':'revenue','live':True}).status_code,403)
    def test_document_ingestion_requires_operator(self):
        self.assertEqual(self.client.post('/api/documents',json={'company':'Test','year':2025,'section':'Revenue','text':'Synthetic revenue was 3 million USD.'}).status_code,403)
    def test_input_limits(self):
        self.assertEqual(self.client.post('/api/answer',json={'question':'x','k':999}).status_code,422)
    def test_metrics_and_trace(self):
        response=self.client.get('/health')
        self.assertEqual(len(response.headers['x-trace-id']),32)
        self.assertIn('http_requests_total',self.client.get('/metrics').text)
    @patch.dict(os.environ,{'ADMIN_API_TOKEN':'test-operator'})
    def test_ingestion_rebuilds_index(self):
        result=self.client.post('/api/documents',headers={'X-Admin-Token':'test-operator'},json={'company':'TestCo','year':2025,'section':'Warranty','text':'The synthetic warranty reserve was 33 million USD in 2025.'})
        self.assertEqual(result.status_code,201)
        self.assertIn('33 million',index.search('warranty reserve','TestCo',2025)[0]['text'])


if __name__=='__main__':unittest.main()
