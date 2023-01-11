import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: Dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    encoding='utf-8',
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
handler.setFormatter(formatter)
LOGGER.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка токенов."""
    errors = []
    if not PRACTICUM_TOKEN:
        LOGGER.critical('Не найден PRACTICUM_TOKEN!')
        errors.append(PRACTICUM_TOKEN)
    if not TELEGRAM_TOKEN:
        LOGGER.critical('Не найден TELEGRAM_TOKEN!')
        errors.append(TELEGRAM_TOKEN)
    if not TELEGRAM_CHAT_ID:
        LOGGER.critical('Не найден TELEGRAM_CHAT_ID!')
        errors.append(TELEGRAM_CHAT_ID)
    return errors


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        LOGGER.debug(f'Сообщение "{message}" отправлено в чат.')
    except Exception as error:
        LOGGER.error(f'Произошла ошибка при отправке соощения: {error}')


def get_api_answer(timestamp):
    """Запрос к ENDPOINT.
    Возвращает формат json для python.
    """
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            LOGGER.error(f'Запрос к ENDPOINT {response.status_code} != 200')
            response.raise_for_status()
    except requests.RequestException as error:
        LOGGER.error(f'Произошла ошибка при запросе к ENDPOINT: {error}'
    LOGGER.debug(
        f'Произошел запрос к ENDPOINT. Код ответа: {response.status_code}.'
    )
    try:
        response_json = response.json()
    except Exception as error:
        LOGGER.error(f'Произошла ошибка при преобразовании в json: {error}')
        raise SystemError
    return response_json


def check_response(response):
    """Проверяет ответ в формате json.
    В случае успеха возвращает словарь с данными
    о последней домашке.
    """
    if not isinstance(response, dict):
        LOGGER.error(
            f'response не словарь: type(response) != {type(response)}.'
        )
        raise TypeError
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        LOGGER.error(f'response не содержит ключ {error}')
    if not isinstance(homeworks, list):
        LOGGER.error(
            f'Список домашек не list: type(homeworks) != {type(homeworks)}.'
        )
        raise TypeError
    if not homeworks:
        LOGGER.error(
            f'Список домашек пуст: len(homeworks) = {len(homeworks)}.'
        )
        raise IndexError
    homework_name = homeworks[0].get('homework_name')
    if not homework_name:
        LOGGER.error(
            f'В домашке нет homework_name. homework_name = {homework_name}'
        )
        raise KeyError
    status = homeworks[0].get('status')
    if not status:
        LOGGER.error(f'В домашке нет status. status = {status}')
        raise KeyError
    return homeworks[0]


def parse_status(homework):
    """Извлекает данные о домашке из словаря."""
    homework_name = homework.get('homework_name')
    LOGGER.debug(f'Получил имя домашки homework_name = {homework_name}')
    if not homework_name:
        LOGGER.error('В ответе нет ключа homework_name')
        raise KeyError
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS.keys():
        LOGGER.error(
            f'Получил недокументированный статус домашки, status = {status}'
        )
        raise KeyError
    verdict = HOMEWORK_VERDICTS[status]
    LOGGER.debug(f'Получил статус домашки status = {status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    statuses = ['reviewing']
    while True:
        if check_tokens() == []:
            try:
                timestamp = int(time.time())
                api_answer = get_api_answer(timestamp)
                check = check_response(api_answer)
                if check:
                    message = parse_status(check)
                    statuses.append(message)
                    if statuses[0] != message:
                        statuses[0] = message
                        LOGGER.debug('Статус работы изменился')
                        LOGGER.debug(f'message = {message}')
                        send_message(bot, message)
                        statuses.pop()
                else:
                    LOGGER.error(
                        f'Не пройдена проверка check_response = {check}'
                    )
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                LOGGER.error(f'Сбой в работе программы: {error}')
            finally:
                time.sleep(RETRY_PERIOD)
        else:
            LOGGER.critical(
                'Не обнаружены переменные окружения!Остановка бота.'
            )
            sys.exit('Не обнаружены переменные окружения! Остановка бота.')


if __name__ == '__main__':
    main()
