import pymysql
import json
import time


def get_leaderboard(number_of_users=10):
    query = 'SELECT COUNT(*) FROM users;'
    cursor.execute(query)
    number = cursor.fetchone()[0]
    fundamentals = get_fundamentals_sort()
    algorithms = get_algorithms_sort()
    result = dict()
    if number < 200:
        result['fundamentals'] = fundamentals
        result['algorithms'] = algorithms
    else:
        result['fundamentals'] = fundamentals[:100]
        result['algorithms'] = algorithms[:100]
    return result


def save_user(email, password, username, verified, verification_code):
    try:
        query = f"""insert users(email, password, username, achievement, avatar, verified, verification_code)
            values ('{email}', '{password}', '{username}', '0', '0', {verified}, '{verification_code}')"""

        cursor.execute(query)
        connection.commit()
        user = user_information(email)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        query = f"""INSERT INTO fundamentals(user_id, testsPassed, totalTests, lastActivity)
            VALUES ('{user['id']}', 0, 0, '{current_time}')"""
        cursor.execute(query)
        connection.commit()
        query = f"""INSERT INTO algorithms(user_id, testsPassed, totalTests, lastActivity)
            VALUES ('{user['id']}', 0, 0, '{current_time}')"""
        cursor.execute(query)
        connection.commit()
        return 'success'
    except pymysql.MySQLError as e:
        return f"Ошибка подключения: {e}"


def get_fundamentals_sort():
    query = f"""SELECT fundamentals.*, users.username, users.achievement, users.avatar
                FROM fundamentals
                JOIN users ON fundamentals.user_id = users.id
                ORDER BY fundamentals.score"""
    cursor.execute(query)
    data = cursor.fetchall()
    records = fund_alg_from_data_to_dct(data)
    return records


def get_algorithms_sort():
    query = f"""SELECT algorithms.*, users.username, users.achievement, users.avatar
                FROM algorithms
                JOIN users ON algorithms.user_id = users.id
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
    user = cursor.fetchone()

    if user is None:
        return 'not_found'
    else:
        dct = {'id': user[0],
                'email': user[1],
                'password': user[2],
                'nickname': user[3],
                'achievement': user[4],
                'avatar': user[5],
                'verified': user[6],
                'verification_code': user[7]
                }
        return dct


def users_from_data_to_dct(data):
    records = dict()
    for i in data:
        records[i[1]] = {'id': i[0],
                 'email': i[1],
                'password': i[2],
                'nickname': i[3],
                'achievement': i[4],
                'avatar': i[5],
                'verified': i[6],
                'verification_code': i[7]
                }
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