import pymysql
import json


with open('database_user.json') as file:
    file_json_data = json.load(file)
try:
    connection = pymysql.connect(
        host=file_json_data['host'],
        user=file_json_data['user'],
        password=file_json_data['password'],
        database=file_json_data['database']
    )
    cursor = connection.cursor()
    query = f"SELECT * FROM users;"  # Запрос для получения всех данных из таблицы
    cursor.execute(query)
    data = cursor.fetchall()
    print(data)
except pymysql.MySQLError as e:
    print(f"Ошибка подключения: {e}")
finally:
    if 'connection' in locals():
        connection.close()