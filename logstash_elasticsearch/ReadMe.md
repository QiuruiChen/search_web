
### 1. Run template for indexes

run `index_templates.txt` content in elasticsearch

### 2.Create Bert dense vector for online pdf

```python
python pdf_to_bert.py
```

### 3.ingest data into elasticsearch through logstash

```bash
logstash -f jdbc_csv_pip.conf
```

It creates two indexes: `idx_content` for data extract from sql server, `idx_attachments` for content extracted from online pdf.

### 4. Search on elasticsearch

run `search_commend.txt` content in elasticsearch


### Note for setting jdbc plugin in logstash

Download the [jdbc driver](https://docs.microsoft.com/en-us/sql/connect/jdbc/using-the-jdbc-driver?view=sql-server-ver15)
Also check [the reqirement](https://docs.microsoft.com/en-us/sql/connect/jdbc/system-requirements-for-the-jdbc-driver?view=sql-server-ver15) for the jdbc driver.

Change the [jdbc plugin](https://www.elastic.co/guide/en/logstash/current/plugins-inputs-jdbc.html) setting:
```
jdbc {
      jdbc_driver_library => "the path to your sqljdbc drivers"
      jdbc_driver_class => "com.microsoft.sqlserver.jdbc.SQLServerDriver"
      jdbc_connection_string => "jdbc:sqlserver://server:port;database=...;user=...;password=..."
      jdbc_user => ".."
      jdbc_password => ".."
      statement => "..."
      use_column_value => true
      #jdbc_fetch_size => 100 #if the retrieved is big, apply this
      tracking_column => "contentId"
      tracking_column_type => "numeric"
      schedule => "0 6 * * * America/Chicago" #will execute at 6:00am (UTC/GMT -5) every day.
      tags => "elasticContent"
}
```
