#! /usr/bin/python
import pyodbc
import os
import pandas as pd
from google.cloud import storage
from datetime import datetime
import tensorflow as tf
from transformers import BertTokenizer, TFBertModel
import json
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import validators
# read file content from pdf
from tika import parser
import argparse
# Directly read content from blob
# https://pypi.org/project/azure-storage-blob/
# https://stackoverflow.com/questions/48881228/azure-blob-read-using-python
# from azure.storage.blob import BlobClient
#
# blob = BlobClient(account_url="https://<account_name>.blob.core.windows.net"
#                   container_name="<container_name>",
#                   blob_name="<blob_name>",
#                   credential="<account_key>")
#
# with open("example.csv", "wb") as f:
#     data = blob.download_blob()
#     data.readinto(f)

## Or read pdf from url
class Docs:
    def __init__(self,datasetname,server,username,password,driver,doc_json,index_mapping,index_name):
        self.datasetname = datasetname
        self.server = server
        self.username = username
        self.password = password
        self.driver = driver
        self.bert_model_name = 'bert-base-multilingual-cased'
        self.max_length = 512

        self.doc_json = doc_json
        self.index_mapping = index_mapping
        self.index_name = index_name

    def _conn_sql_service(self,sql_script):

        cnxn = pyodbc.connect('DRIVER='+self.driver+';SERVER='+self.server+';PORT=1433;DATABASE='+self.datasetname+';UID='+self.username+';PWD='+ self.password)

        cursor = cnxn.cursor()
        # get all tabels from the database
        cursor.execute(sql_script)
        self.attach_list = cursor.fetchall()

    def _pre_process_links(self):
        # remove null and png list
        attach_list = [attach for attach in self.attach_list
                       if ((attach[1] is not None) and
                       any("pdf" in s for s in [attach_url.strip()[-3:] for attach_url in (attach[1].strip().split(','))]))]
        # expload data for each pdf
        contentIds = [attach[0] for attach in attach_list]
        url_list = [attach[1].strip().split(',') for attach in attach_list]

        self.df = pd.DataFrame(data={'contentId': contentIds,
                                     'urls': url_list,
                                     })
        self.df = self.df.explode('urls')
        self.df = self.df[self.df['urls'].map(lambda x:x.strip()[-3:]) == 'pdf']
        # replace white space with %20
        self.df['urls'] = self.df['urls'].apply(lambda x:x.strip().replace(" ","%20"))
        # remove unvalid url

        self.df= self.df[self.df['urls'].apply(lambda x:validators.url(x)) == True]

    def _extract_content_from_pdf(self):
        pdf_content = []
        url_list = self.df['urls'].to_list()
        for url in url_list:
            try:
                pdf_content.append(parser.from_file(url)['content'])
            except:
                pdf_content.append(None)

        assert len(pdf_content) == len(url_list)
        self.df['pdf_content'] = [pdf.replace("\n","") if pdf is not None else None for pdf in pdf_content]

        self.docs = []
        self.df['pdf_content'] = self.df['pdf_content'].fillna("")
        for row in self.df.iterrows():
            series = row[1]
            doc = {
                'url': series.urls,
                'text': series.pdf_content,
                "contentId":series.contentId,

            }
            self.docs.append(doc)

    # Gneerate data in bulk format: https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html
    def _create_document(self,doc, emb):
        return {
            '_op_type': 'index',
            '_index': self.index_name,
            'text': doc['text'],
            'url': doc['url'],
            'contentId':doc['contentId'],
            'text_vector': emb
        }

    def _bulk_predict(self, batch_size=256):
        """Predict bert embeddings."""
        for i in range(0, len(self.docs), batch_size):
            batch_docs = self.docs[i: i+batch_size]
            tokenizer = BertTokenizer.from_pretrained(self.bert_model_name)
            model = TFBertModel.from_pretrained(self.bert_model_name)
            text_list = [doc['text'] for doc in batch_docs]

            batch_encoding = tokenizer.batch_encode_plus(
                text_list, max_length=self.max_length, pad_to_max_length=True,
            )
            features = []
            for i in range(len(text_list)):
                inputs = {k: batch_encoding[k][i] for k in batch_encoding}
                features.append(inputs['input_ids'])

            features = tf.convert_to_tensor(features)
            outputs = model(features) # shape: (batch,sequence length, hidden state)
            embeddings = tf.reduce_mean(outputs[0],1)

            # embeddings = bc.encode([doc['text'] for doc in batch_docs])
            for emb in embeddings:
                yield emb.numpy().tolist()

    def _docs_into_json(self):
        with open(self.doc_json, 'w') as f:
            for doc, emb in zip(self.docs, self._bulk_predict(self.docs)):
                d = self._create_document(doc, emb)
                f.write(json.dumps(d) + '\n')


    def gen_docs(self,sql_script):
        '''generate the correct format jsonl document file'''
        self._conn_sql_service(sql_script) # connnect sql to get data
        self._pre_process_links()          # preprocess the data
        self._extract_content_from_pdf()   # extract pdf content from urls
        self._docs_into_json()             # convert to json


    def _load_json_docs(self):
        with open(self.doc_json) as f:
            return [json.loads(line) for line in f]

    def indexing_files(self):
        # create index
        # https://elasticsearch-py.readthedocs.io/en/master/
        # es = Elasticsearch(['https://user:secret@localhost:443'])
        client = Elasticsearch(['https://elastic:.....@d738b05373084f7bb48b4287c81bb5d2.westeurope.azure.elastic-cloud.com:9243'])
        client.indices.delete(index=self.index_name, ignore=[404])
        with open(self.index_mapping) as index_file:
            source = index_file.read().strip()
            client.indices.create(index=self.index_name, body=source)

        # index document
        docs = self._load_json_docs()
        # update: https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html
        bulk(client, docs)



def main(args):
    docs = Docs(args.databasename,
                args.server,args.username,
                args.password,args.driver,
                args.doc_json,
                args.index_mapping,
                args.index_name)
    docs.gen_docs(args.sql_script)
    docs.indexing_files()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Creating elasticsearch documents and indexing them')
    parser.add_argument('--databasename',
                        default="Buddie-Search-Testing",
                        help='databasename')
    parser.add_argument('--server',
                        default='ontwikkel-db.database.windows.net',
                        help='azure sql server server')
    parser.add_argument('--username',
                        default="username",
                        help='azure sql server username')
    parser.add_argument('--password',
                        default='....',
                        help='azure sql server password')
    parser.add_argument('--driver',
                        default='{ODBC Driver 17 for SQL Server}',
                        help='driver for azure sql server')
    parser.add_argument('--doc_json',
                        default='docs.jsonl',
                        help='elasticsearch saved doc jsonl file')
    parser.add_argument('--index_mapping',
                        default='idx_attachments_mapping.json',
                        help='Elasticsearch index mapping.')
    parser.add_argument('--index_name',
                        default='idx_attachments',
                        help='Elasticsearch index name.')
    parser.add_argument('--sql_script',
                        default="SELECT [contentId],[attachments] FROM [dbo].[vwAzureSearchIndex] WHERE [gepubliceerd] =1",
                        help='sql for collecting data from azure sql server')
    args = parser.parse_args()
    main(args)



