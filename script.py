import os
from datetime import datetime

import psycopg2
import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# Google Sheets API credentials
scopes = ['https://www.googleapis.com/auth/spreadsheets']
secret_file = 'credentials.json'
spreadsheet_id = '1G32atHixJ6NappzNsYO4JZYwl7GeO5_MTMHXrBrPQqg'
range_name = 'A:E'

# PostgreSQL database credentials
db_host = os.getenv('DB_HOST', default=None)
db_port = os.getenv('DB_PORT', default=None)
db_name = os.getenv('POSTGRES_DB', default='postgres')
db_user = os.getenv('POSTGRES_USER', default=None)
db_password = os.getenv('POSTGRES_PASSWORD', default=None)


def get_exchange_rate():
    """
    This function gets the USD to RUB exchange rate from the Bank of Russia website.
    """
    url = 'https://www.cbr.ru/scripts/XML_daily.asp'
    response = requests.get(url)
    rate = response.text.split('<Valute ID="R01235">')[1].split('<Value>')[
        1].split('</Value>')[0].replace(',', '.')
    return float(rate)


def get_google_sheets_data():
    """
    This function gets data from the specified range of Google Sheets.
    """
    try:
        credentials = service_account.Credentials.from_service_account_file(
            secret_file, scopes=scopes)
        service = build('sheets', 'v4', credentials=credentials)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        return result.get('values', [])
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def insert_data_into_database():
    """
    This function inserts data into PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(
            host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)
        cur = conn.cursor()
        cur.execute(
            'CREATE TABLE IF NOT EXISTS data (id SERIAL PRIMARY KEY, name TEXT, price FLOAT, quantity INTEGER, date TIMESTAMP)')
        conn.commit()

        for row in get_google_sheets_data():
            name = row[0]
            quantity = int(row[1])
            price_usd = float(row[2])
            date = datetime.strptime(row[3], '%m/%d/%Y %H:%M:%S')
            exchange_rate = get_exchange_rate()
            price_rub = price_usd * exchange_rate
            cur.execute('INSERT INTO data (name, price, quantity, date) VALUES (%s, %s, %s, %s)',
                        (name, price_rub, quantity, date))

        conn.commit()
        print('Data has been inserted into the database.')
    except psycopg2.Error as error:
        print(f'An error occurred: {error}')
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    while True:
        insert_data_into_database()
