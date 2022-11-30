   
from datetime import timedelta, datetime
import pandas as pd
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import timedelta
from airflow.utils.dates import days_ago
import requests
import csv
import json
import psycopg2 as pg

# Operators
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator

# initializing the default arguments

args={'owner': 'airflow'}

default_args = {
        'owner': 'airflow',    
        #'start_date':datetime(2022, 3, 4),
        # 'end_date': datetime(),
        # 'depends_on_past': False,
        #'email': ['airflow@example.com'],
        #'email_on_failure': False,
        # 'email_on_retry': False,
        # If a task fails, retry it once after waiting
        # at least 5 minutes
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        }

# Instantiate a DAG object

# python callable function
def getDataToLocal():
  url = "https://data.covid19.go.id/public/api/update.json" 
  covid_data = pd.read_json(url)
  listCovid = covid_data.at['harian','update']
  covid_df=pd.DataFrame(listCovid)
  covid_df = covid_df.set_index("key")
  covid_df.to_csv("/opt/airflow/data/covid.csv", sep=',' ,escapechar='\\', quoting=csv.QUOTE_NONE, encoding='utf-8' )

def transformData():
    dataframe = pd.read_csv("/opt/airflow/data/covid.csv")
    dataframe.iloc[:,2:11] = dataframe.iloc[:,2:11].replace(to_replace= '[a-z]+', value = '', regex =True)
    dataframe.iloc[:,2:11] = dataframe.iloc[:,2:11].replace(to_replace= '[^\w\s]', value = '', regex =True)
    dataframe.iloc[:,2:11] = dataframe.iloc[:,2:11].astype('int')
    dataframe['key_as_string'] = dataframe['key_as_string'].astype('datetime64')
    dataframe = dataframe.set_index("key")
    dataframe.to_csv("/opt/airflow/data/covid.csv", sep=',' ,escapechar='\\', quoting=csv.QUOTE_NONE, encoding='utf-8' )
    
    
    


def creatableLoad():
    def checkdate(dbconnect):
      testcursor = dbconnect.cursor()
      testcursor.execute("""
        SELECT DISTINCT key_as_string
        FROM covid_data;
      """
      )

      data = pd.read_csv('/opt/airflow/data/covid.csv')
      y = str(data["key"][0])

      check = True
      myresult = testcursor.fetchall()
      for x in myresult:
        z = x[0].replace('"', "")
        if (z == y):
          check = False
      
      return(check)
  
    try:
        dbconnect = pg.connect(
            "dbname='airflow' user='airflow' host='airflow-postgres-1' password='airflow'"
        )
    except Exception as error:
        print(error)
    # create the table if it does not already exist
    cursor = dbconnect.cursor()
    cursor.execute("""
         CREATE TABLE IF NOT EXISTS covid_data (         
            key varchar(50),
            key_as_string date,
            doc_count int,
            jumlah_meninggal int,
            jumlah_sembuh int,
            jumlah_positif int,
            jumlah_dirawat int,
            jumlah_positif_kum int,
            jumlah_sembuh_kum int,
            jumlah_meninggal_kum int,
            jumlah_dirawat_kum int
        );
        
        TRUNCATE TABLE covid_data;
    """
    )
    dbconnect.commit()
    
    check= checkdate(dbconnect)
    if check:
    # insert each csv row as a record in our database
        with open('/opt/airflow/data/covid.csv', 'r') as f:
            next(f)  # skip the first row (header)     
            for row in f:
                cursor.execute("""
                    INSERT INTO covid_data
                    VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')
                """.format(
                row.split(",")[0],
                row.split(",")[1],
                row.split(",")[2],
                row.split(",")[3],
                row.split(",")[4],
                row.split(",")[5],
                row.split(",")[6],
                row.split(",")[7],
                row.split(",")[8],
                row.split(",")[9],
                row.split(",")[10])
                )
    dbconnect.commit()

dag_pandas = DAG(
  dag_id = "Covid_dags",
  default_args=default_args ,
  # schedule_interval='0 0 * * *',
  schedule_interval='@daily',	
  dagrun_timeout=timedelta(minutes=60),
  description='use case of pandas  in airflow',
  start_date = days_ago(1))

getDataToLocal = PythonOperator(task_id='getDataToLocal', python_callable=getDataToLocal, dag=dag_pandas)
transformData = PythonOperator(task_id='transformData', python_callable=transformData, dag=dag_pandas)
creatableLoad = PythonOperator(task_id='creatableLoad', python_callable=creatableLoad, dag=dag_pandas)
getDataToLocal>>transformData>>creatableLoad

if __name__ == '__main__ ':
  dag_pandas.cli()
# Set the order of execution of tasks. 
