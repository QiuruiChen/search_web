#! /usr/bin/python
import pyodbc
import os
import pandas as pd
from google.cloud import storage
from datetime import datetime
import tensorflow as tf
from transformers import BertTokenizer, TFBertModel
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
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/rachelchen/Documents/data/eci-workspace-rachel-c0ec597f4492.json'

def conn_sql_service():
    DATASETNAME = "Buddie-Search-Testing"
    SERVER = 'ontwikkel-db.database.windows.net'

    username = 'username'
    password = '....'
    driver= '{ODBC Driver 17 for SQL Server}'

    cnxn = pyodbc.connect('DRIVER='+driver+';SERVER='+SERVER+';PORT=1433;DATABASE='+DATASETNAME+';UID='+username+';PWD='+ password)

    cursor = cnxn.cursor()
    # get all tabels from the database
    cursor.execute("SELECT [contentId],[attachments] FROM [dbo].[vwAzureSearchIndex]")
    attach_list = cursor.fetchall()
    return attach_list


def pre_process_links(attach_list):
    # remove null and png list
    attach_list = [attach for attach in attach_list
                   if ((attach[1] is not None) and
                   any("pdf" in s for s in [attach_url.strip()[-3:] for attach_url in (attach[1].strip().split(','))]))]
    # expload data for each pdf
    contentId_list = [attach[0] for attach in attach_list]
    url_list = [attach[1].strip().split(',') for attach in attach_list]

    df = pd.DataFrame(data={'contentId': contentId_list, 'urls': url_list})
    df = df.explode('urls')
    df = df[df['urls'].map(lambda x:x.strip()[-3:]) == 'pdf']
    # replace white space with %20
    df['urls'] = df['urls'].apply(lambda x:x.strip().replace(" ","%20"))
    # remove unvalid url
    import validators
    df= df[df['urls'].apply(lambda x:validators.url(x)) == True]
    return df


def extract_content_from_pdf(df):
    # read file content from pdf
    from tika import parser

    pdf_content = []
    url_list = df['urls'].to_list()
    for url in url_list:
        try:
            pdf_content.append(parser.from_file(url)['content'])
        except:
            pdf_content.append(None)

    assert len(pdf_content) == len(url_list)
    df['pdf_content'] = [pdf.replace("\n","") if pdf is not None else None for pdf in pdf_content]
    return df

def extract_bert_feature(df):
    tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-cased')
    model = TFBertModel.from_pretrained('bert-base-multilingual-cased')
    # input_ids = tf.constant(tokenizer.encode("Injecteren intramusculairProtocollen Voorbehouden, Risicovolle en Overige handelingen Injecteren algemeen 100   Injecteren intramusculair Omschrijving Het voorgeschreven medicijn wordt (zo nodig) opgelost en opgetrokken in een spuit. Vervolgens wordt het medicijn loodrecht in een spier gespoten.  Opdracht tot voorbehouden of risicovolle handeling:  Mag zelfstandig verricht worden door:      Aandachtspunten - In deze geprotocolleerde werkinstructie wordt ervan uitgegaan dat het medicijn met een opzuignaald uit een flacon of ampul wordt opgetrokken en wordt toegediend met een injectienaald. - Geschikte injectieplaatsen zijn: de buiten/bovenkant van resp. de bovenarm (musculus deltoïdeus), het bovenbeen (musculus lateralis) en de bil (musculus glutaeus). - Indien de patiënt vaker een intramusculaire injectie krijgt, wissel dan iedere keer van injectieplaats. - Palpeer en controleer de injectieplaats op geschiktheid. - Het intramusculair inspuiten van een relatief grote hoeveelheid vloeistof (meer dan 5 ml) op één plaats kan pijnlijk zijn. Verdeel de totale hoeveelheid zo nodig over twee injectieplaatsen. - Het achteraf afdrukken en/of masseren van de injectieplaats dient achterwege te blijven. - Deze geprotocolleerde werkinstructie is niet van toepassing op het injecteren van cytostatica. - Het werken met een overzichtelijke medicijnlijst waarop per tijdstip wordt aangegeven welke medicijnen moeten worden toegediend reduceert het maken van fouten. - Van een verkeerd toegediend en/of een niet gegeven injectie dient melding te worden gemaakt volgens organisatieprocedure. Informeer arts.   Complicaties tijdens de handeling Handelwijze Misselijkheid door te snel injecteren. Rustig, niet te snel injecteren. Tijdens het terugtrekken van de zuiger wordt bloed opgetrokken.  Trek de naald eruit en druk de injectieplaats af met een gaasje. Neem een nieuwe spuit en naald en begin opnieuw. Kies een andere injectieplaats. Tijdens het injecteren raakt naald los van spuit.  Afhankelijk van soort injectie de injectie overdoen.  Tijdens het injecteren raakt naald subcutaan. Let op heftige lokale reacties.  Verwijzingen - Achtergrondinformatie: injecteren. - Materiaalbeschrijvingen: injectienaalden; injectiespuiten. - Hygiënerichtlijnen: desinfecteren bij injecties, gebruik naaldenbeker. - Geprotocolleerde werkinstructie: gereedmaken injectiespuit (ampul), gereedmaken injectiespuit (flacon). Benodigdheden - flacon of ampul met het voorgeschreven medicijn - gaasjes  - steriele spuit - steriele opzuignaald - steriele injectienaald - prullenbak - naaldenbeker Indien het medicijn in een flacon met rubber dop zit: - desinfectans, chloorhexidine alcohol 70%  Indien het medicijn in de flacon nog moet worden opgelost: - ampul met oplosmiddel - gaasje (om de ampul open te breken) © Vilans 03-05-2009 Injecteren intramusculair: 1 (van 2) KICK  onbewaakte kopieProtocollen Voorbehouden, Risicovolle en Overige handelingen Injecteren algemeen 101   © Vilans 03-05-2009 Injecteren intramusculair: 2 (van 2) KICK Werkwijze 1 Pas handhygiëne toe. 2 Zet de benodigdheden binnen handbereik. 3 Controleer het medicijn, de medicijnlijst en de gegevens van de cliënt. a Controleer het medicijn op de volgende aspecten: - vervaldatum - kleur en substantie - toedieningswijze b Vergelijk het medicijn met de medicijnlijst. - naam en geboortedatum cliënt  - soort - dosering - toedieningstijdstip 4 Maak het medicijn klaar voor gebruik. Indien het medicijn in een ampul zit: a Breek de ampul open met een gaasje als bescherming. Indien het medicijn in een flacon met rubber dop zit:  a Overgiet een gaasje met alcohol. b Desinfecteer het rubber met het alcoholgaasje en laat gedurende 1 minuut drogen. Indien het medicijn nog moet worden opgelost: a Breek de ampul oplosmiddel open met een gaasje als bescherming. b Trek de juiste hoeveelheid oplosmiddel op. c Spuit het oplosmiddel in de flacon met het medicijn; laat de naald + spuit in de flacon zitten. d Wacht tot het medicijn geheel is opgelost. Laat hierbij de zuiger van de spuit iets vieren. 5 Maak de spuit met het medicijn gereed. a Zuig de voorgeschreven hoeveelheid medicatie op in de spuit met behulp van opzuignaald. b Ontlucht de spuit. c Doe de opzuignaald in de naaldenbeker. d Plaats de injectienaald op de spuit. 6 Vraag de patiënt de injectieplaats te ontbloten en zich te ontspannen. 7 Neem de spuit in de injecterende hand en verwijder de naaldhuls. 8 Span de huid met de duim en wijsvinger van uw vrije hand. 9 Steek de naald met een snelle beweging loodrecht op het oppervlak in de spier. 10 Laat de huid los. 11 Trek de zuiger iets terug om u ervan te vergewissen dat er geen bloedvat is aangeprikt. 12 Spuit de vloeistof langzaam en regelmatig in. 13 Trek de naald uit de huid (houd gaasje gereed voor de opvang van een eventuele bloeddruppel; niet afdrukken of masseren!). 14 Doe de naald in de naaldenbeker. 15 Ruim de overige materialen op. 16 Noteer tijdstip, soort, concentratie, hoeveelheid, plaats, wijze van toediening en bevindingen.  onbewaakte kopie", add_special_tokens=True))[None, :]  # Batch size 1
    text_list = df['pdf_content'].fillna("").to_list()
    max_length = 768

    batch_encoding = tokenizer.batch_encode_plus(
        text_list, max_length=max_length, pad_to_max_length=True,
    )
    features = []
    for i in range(len(text_list)):
        inputs = {k: batch_encoding[k][i] for k in batch_encoding}
        features.append(inputs['input_ids'])

    features = tf.convert_to_tensor(features)
    outputs = model(features) # shape: (batch,sequence length, hidden state)
    last_hidden_states = tf.reduce_mean(outputs[0],1) # or tf.reduce_mean(outputs[0],2) avergae at the hidden_state, to get sementic mearning

    df['bert_vector'] = last_hidden_states.numpy().tolist()
    return df

def save_df_to_csv(df,save_path=""):
    # save csv file locally
    if save_path == "":
        save_path = 'data/all_attach_'+datetime.now().strftime('%Y-%m-%d-%H-%M-%S')+'.csv'

    df[['contentId','bert_vector','urls']].to_csv(save_path,index = False,sep=';')
    df.to_csv(save_path,index = False,sep=';')


# upload into gcs
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # bucket_name = "your-bucket-name"
    # source_file_name = "local/path/to/file"
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(
        "File {} uploaded to {}.".format(
            source_file_name, destination_blob_name
        )
    )


attach_list = conn_sql_service()
df = pre_process_links(attach_list)
df = extract_bert_feature(df)
SAVE_PATH = 'data/doc.csv'
save_df_to_csv(df,SAVE_PATH)

# upload_blob('elastic_edcare','attach_'+datetime.now().strftime('%Y-%m-%d-%H-%M-%S')+'.csv',
#             'attach_'+datetime.now().strftime('%Y-%m-%d-%H-%M-%S')+'.csv')


