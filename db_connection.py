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
    if number < 100:
        result['fundamentals'] = fundamentals
        result['algorithms'] = algorithms
    else:
        result['fundamentals'] = fundamentals[:100]
        result['algorithms'] = algorithms[:100]
    return result


def save_user(email, password, username, verified, verification_code):
    try:
        user_query = """
            INSERT INTO users(email, password, username, achievement, avatar, verified, verification_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(user_query, (email, password, username, '0', '0', verified, verification_code))
        connection.commit()

        user = user_information(email)
        if user == 'not_found':
            return 'Ошибка: пользователь не создан'

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        fundamentals_query = """
            INSERT INTO fundamentals(user_id, testsPassed, totalTests, lastActivity)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(fundamentals_query, (user['id'], 0, 0, current_time))

        algorithms_query = """
            INSERT INTO algorithms(user_id, testsPassed, totalTests, lastActivity)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(algorithms_query, (user['id'], 0, 0, current_time))
        connection.commit()
        return 'success'

    except pymysql.MySQLError as e:
        connection.rollback()
        return f"Ошибка подключения: {e}"


def get_fundamentals_sort():
    query = """SELECT fundamentals.*, users.username, users.achievement, users.avatar
                FROM fundamentals
                JOIN users ON fundamentals.user_id = users.id
                ORDER BY fundamentals.score"""
    cursor.execute(query)
    data = cursor.fetchall()
    records = fund_alg_from_data_to_dct(data)
    return records


def get_algorithms_sort():
    query = """SELECT algorithms.*, users.username, users.achievement, users.avatar
                FROM algorithms
                JOIN users ON algorithms.user_id = users.id
                ORDER BY algorithms.score;"""
    cursor.execute(query)
    data = cursor.fetchall()
    records = fund_alg_from_data_to_dct(data)
    return records


def change_db_users(email, *args):
    try:
        for column, new_value in args:
            query = "UPDATE users SET %s = %s WHERE email = %s"
            valid_columns = ['password', 'nickname', 'achievement',
                             'avatar', 'verified', 'verification_code']
            if column not in valid_columns:
                return f"Ошибка: недопустимое имя столбца {column}"
            cursor.execute(query, (column, new_value, email))
        connection.commit()
        return 'success'
    except pymysql.MySQLError as e:
        connection.rollback()
        return f"Ошибка подключения: {e}"


def user_information(email):
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user is None:
        return None
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