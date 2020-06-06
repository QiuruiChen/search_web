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
# from tika import parser
import tika
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
        # [contentId],[attachments],[titel],[omschrijving],[tekst],[auteur],[jaarPublicatie],[pakketNamen],[themaNamen],[tagNamen],[documentNamen],[classificatieNaam],[typeNaam],[aangemaaktDoor], [aangemaaktOp],[duur],[beoordeling],[aantalBeoordelingen],[pageviews],[timestamp],[organisatieId]
        contentIds = [attach[0] for attach in attach_list]
        url_list = [attach[1].strip().split(',') for attach in attach_list]
        # enrich into 5 element for each url list
        for item in url_list:
            for _ in range(0,5-len(item)):
                item.append("")
        #if more than 5 attachments, delete the remained attachments
        url_list = [item[0:5] for item in url_list]

        assert [len(item)==5 for item in url_list]

        titels = [attach[2] for attach in attach_list]
        omschrijvings = [attach[3] for attach in attach_list]
        teksts = [attach[4] for attach in attach_list]
        auteurs = [attach[5] for attach in attach_list]
        jaarPublicaties = [attach[6] for attach in attach_list]
        pakketNamens = [attach[7] for attach in attach_list]
        themaNamens = [attach[8] for attach in attach_list]
        tagNamens = [attach[9] for attach in attach_list]
        documentNamens = [attach[10] for attach in attach_list]
        classificatieNaams = [attach[11] for attach in attach_list]
        typeNaams = [attach[12] for attach in attach_list]
        aangemaaktDoors = [attach[13] for attach in attach_list]
        aangemaaktOps = [attach[14] for attach in attach_list]
        duurs = [attach[15] for attach in attach_list]
        beoordelings = [attach[16] for attach in attach_list]
        aantalBeoordelingens = [attach[17] for attach in attach_list]
        pageviewss = [attach[18] for attach in attach_list]
        timestamps = [attach[19] for attach in attach_list]
        organisatieIds = [attach[20] for attach in attach_list]


        self.df = pd.DataFrame(data={'contentId': contentIds,
                                     'urls': url_list,
                                     'titel':titels,
                                     'omschrijving':omschrijvings,
                                     'tekst':teksts,
                                     'auteur':auteurs,
                                     'jaarPublicatie':jaarPublicaties,
                                     'pakketNamen':pakketNamens,
                                     'themaNamen':themaNamens,
                                     'tagNamen':tagNamens,
                                     'documentNamen':documentNamens,
                                     'classificatieNaam':classificatieNaams,
                                     'typeNaam':typeNaams,
                                     'aangemaaktDoor':aangemaaktDoors,
                                     'aangemaaktOp':aangemaaktOps,
                                     'duur':duurs,
                                     'beoordeling':beoordelings,
                                     'aantalBeoordelingen':aantalBeoordelingens,
                                     'pageviews':pageviewss,
                                     'timestamp':timestamps,
                                     'organisatieId':organisatieIds
                                     })

        self.df[['attach_url1','attach_url2','attach_url3','attach_url4','attach_url5']] = pd.DataFrame(self.df.urls.tolist(), index= self.df.index)

        # self.df = self.df.explode('urls')
        # self.df = self.df[self.df['urls'].map(lambda x:x.strip()[-3:]) == 'pdf']
        # replace white space with %20
        self.df[['attach_url1','attach_url2','attach_url3','attach_url4','attach_url5']] = self.df[['attach_url1','attach_url2','attach_url3','attach_url4','attach_url5']].applymap(lambda x:x.strip().replace(" ","%20"))
        # remove unvalid url
        self.df[['attach_url1','attach_url2','attach_url3','attach_url4','attach_url5']] = self.df[['attach_url1','attach_url2','attach_url3','attach_url4','attach_url5']].applymap(lambda x: x if validators.url(x) == True else "")

        # correct date
        self.df['aangemaaktOp'] = self.df['aangemaaktOp'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))

        # remove na data, nan cause elasticsearch index problem
        self.df.dropna(inplace=True)


    def _read_pdf_content(self,url_col,pdf_col):
        pdf_content = []
        url_list = self.df[url_col].to_list()
        for url in url_list:
            if url.strip()[-3:] == 'pdf':
                try:
                    pdf_content.append(tika.parser.from_file(url)['content'])
                except:
                    pdf_content.append(None)
            else:
                pdf_content.append(None)

        assert len(pdf_content) == len(url_list)
        self.df[pdf_col] = [pdf.replace("\n","") if pdf is not None else None for pdf in pdf_content]
        self.df[pdf_col] = self.df[pdf_col].fillna("")

    def _extract_content_from_pdf(self):
        self._read_pdf_content('attach_url1','attachment_text1')
        self._read_pdf_content('attach_url2','attachment_text2')
        self._read_pdf_content('attach_url3','attachment_text3')
        self._read_pdf_content('attach_url4','attachment_text4')
        self._read_pdf_content('attach_url5','attachment_text5')

        self.docs = []

        for row in self.df.iterrows():
            series = row[1]
            doc = {
                '_op_type': 'index',
                '_index': self.index_name,
                'attach_url1': series.attach_url1,
                'attachment_text1': series.attachment_text1,
                'attach_url2': series.attach_url2,
                'attachment_text2': series.attachment_text2,
                'attach_url3': series.attach_url3,
                'attachment_text3': series.attachment_text3,
                'attach_url4': series.attach_url4,
                'attachment_text4': series.attachment_text4,
                'attach_url5': series.attach_url5,
                'attachment_text5': series.attachment_text5,
                "contentId":series.contentId,
                'titel':series.titel,
                'omschrijving':series.omschrijving,
                'tekst':series.tekst,
                'auteur':series.auteur,
                'jaarPublicatie':series.jaarPublicatie,
                'pakketNamen':series.pakketNamen,
                'themaNamen':series.themaNamen,
                'tagNamen':series.tagNamen,
                'documentNamen':series.documentNamen,
                'classificatieNaam':series.classificatieNaam,
                'typeNaam':series.typeNaam,
                'aangemaaktDoor':series.aangemaaktDoor,
                'aangemaaktOp':series.aangemaaktOp,
                'duur':series.duur,
                'beoordeling':series.beoordeling,
                'aantalBeoordelingen':series.aantalBeoordelingen,
                'pageviews':series.pageviews,
                'timestamp_avg':series.timestamp,
                'organisatieId':series.organisatieId
            }
            self.docs.append(doc)

    def _docs_into_json(self):
        with open(self.doc_json, 'w') as f:
            for doc in self.docs:
                f.write(json.dumps(doc, default=str) + '\n')

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
                        default='./doc.jsonl',
                        help='elasticsearch saved doc jsonl file')
    parser.add_argument('--index_mapping',
                        default='./idx_fulltext_mapping.json',
                        help='Elasticsearch index mapping.')
    parser.add_argument('--index_name',
                        default='idx_keyword_search',
                        help='Elasticsearch index name.')
    parser.add_argument('--sql_script',
                        default="SELECT [contentId],[attachments],[titel],[omschrijving],[tekst],[auteur],[jaarPublicatie],[pakketNamen],[themaNamen],[tagNamen],[documentNamen],[classificatieNaam],[typeNaam],[aangemaaktDoor],[aangemaaktOp],[duur],[beoordeling],[aantalBeoordelingen],[pageviews],[timestamp],[organisatieId] FROM [dbo].[vwAzureSearchIndex] WHERE [gepubliceerd] =1",
                        help='sql for collecting data from azure sql server')
    args = parser.parse_args()
    main(args)
