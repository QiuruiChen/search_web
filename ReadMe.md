# Elasticsearch on website:

## Aim: Elasticsearch on data from sql server

Search from
    - Fileds in sql table
    - extracted content from online pdf

Methods:
    - key word search
    - semantic search (similarity between query and text bert feature vectors)

### Data ingestion solutions:

Solution1: Applying [logstash](./logstash_elasticsearch) to bulk data into elasticsearch

Solution 2: Run [python functionto](./FaaS_elasticsearch) bulk data into elasticsearch

