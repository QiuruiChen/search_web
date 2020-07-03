### FaaS(could us google function, auzre function etc) to schedule elasticsearch pipeline.

Bert_vector_search: only read only pdf, extract text into bert features and calculate vectors similarity between query and bert_features.

Full_text_search: key word search on html page and extracted pdf content.

Full_text_search_docker:
    - example [elasticsearch composer file](https://github.com/elastic/elasticsearch/blob/master/distribution/docker/docker-compose.yml)
    - steps:
        -  change the secretes in `db_dtaabase.txt`, `db_passwords.txt`,`db_server.txt` and `db_user.txt`
        - `docker system prune`
        - `docker-compose up --build`


