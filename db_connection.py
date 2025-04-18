import pymysql
import json


def get_leaderboard(number_of_users):
    fundamentals = get_fundamentals_sort()
    algorithms = get_algorithms_sort()
    result = dict()
    if number_of_users < 200:
        result['fundamentals'] = fundamentals
        result['algorithms'] = algorithms
    else:
        result['fundamentals'] = fundamentals[:100]
        result['algorithms'] = algorithms[:100]
    return result


def get_dict_users():
    query = f"SELECT * FROM users;"  # Запрос для получения всех данных из таблицы
    cursor.execute(query)
    data = cursor.fetchall()
    records = users_from_data_to_dct(data)
    return records

def save_user(email, password, nickname, verified, verification_code):
    try:
        query = f"""insert users(email, password, nickname, achievement, avatar, fundamentals, algorithms, verified, verification_code)
            values ('{email}', '{password}', '{nickname}', '123', 'aaa', 0, 0, {verified}, '{verification_code}')"""
        cursor.execute(query)
        connection.commit()
        return 'success'
    except pymysql.MySQLError as e:
        return f"Ошибка подключения: {e}"


def get_fundamentals_sort():
    query = f"""SELECT fundamentals.*, users.nickname, users.achievement, users.avatar
                FROM fundamentals
                JOIN users ON fundamentals.users_id = users.id
                ORDER BY fundamentals.score"""
    cursor.execute(query)
    data = cursor.fetchall()
    records = fund_alg_from_data_to_dct(data)
    return records


def get_algorithms_sort():
    query = f"""SELECT algorithms.*, users.nickname, users.achievement, users.avatar
                FROM algorithms
                JOIN users ON algorithms.users_id = users.id
                ORDER BY algorithms.score;"""
    cursor.execute(query)
    data = cursor.fetchall()
    records = fund_alg_from_data_to_dct(data)
    return records



def change_db_users(email, *args):
    try:
        for i in args:
            query = f"""UPDATE users 
                SET {i[0]} = '{i[1]}'
                WHERE email = '{email}';"""
            cursor.execute(query)
        connection.commit()
        return 'success'
    except pymysql.MySQLError as e:
        return f"Ошибка подключения: {e}"


def user_information(email):
    cursor.execute(f"SELECT * FROM users WHERE email = '{email}';")
    data = cursor.fetchall()
    if len(data) == 0:
        return 'not_found'
    if len(data) > 1:
        return 'found_more'
    return users_from_data_to_dct(data)

def users_from_data_to_dct(data):
    records = list()
    for i in data:
        records.append({'id': i[0],
                 'email': i[1],
                'password': i[2],
                'nickname': i[3],
                'achievement': i[4],
                'avatar': i[5],
                'fund_id': i[6],
                'algo_id': i[7],
                'verified': i[8],
                'verification_code': i[9]
                })
    return records

def fund_alg_from_data_to_dct(data):
    records = []
    for i in data:
        records.append({
            'id':          i[0],
            'user_id':     i[1],
            'score':       i[2],
            'testPassed':  i[3],
            'totalTests':  i[4],
            'lastActivity':i[5],
        })
    return records

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
except pymysql.MySQLError as e:
    print(f"Ошибка подключения: {e}")
# finally:
#     if 'connection' in locals():
#         connection.close()