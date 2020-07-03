FROM python:3.6

RUN mkdir -p /app
WORKDIR /app
COPY . /app

# install packages for sql server connectors in Ubuntu
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

#Download appropriate package for the OS version
#Choose only ONE of the following, corresponding to your OS version

#Ubuntu 16.04
# RUN curl https://packages.microsoft.com/config/ubuntu/16.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

#Ubuntu 18.04
RUN curl https://packages.microsoft.com/config/ubuntu/18.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

#Ubuntu 19.10
#curl https://packages.microsoft.com/config/ubuntu/19.10/prod.list > /etc/apt/sources.list.d/mssql-release.list


RUN apt-get update
RUN ACCEPT_EULA=Y apt-get -y install msodbcsql17
# optional: for bcp and sqlcmd
RUN ACCEPT_EULA=Y apt-get -y install mssql-tools
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc
RUN . ~/.bashrc
# optional: for unixODBC development headers
RUN apt-get -y install unixodbc-dev


RUN pip install -U pip
RUN pip install -r requirements.txt

ENTRYPOINT [ "python" ]
CMD [ "indexer.py" ]
