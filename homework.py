import os
import time
import requests
import sys
import datetime

import telegram
import logging
from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import NotTokenException, NotStatusOkException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: Ты справился, юный падаван !',
    'reviewing': 'Работа взята на проверку.',
    'rejected': 'Работа проверена: ты не туда воевал, переделывай.'
}


def send_message(bot, message):
    """Отправляет сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(
            f'Сообщение в Telegram отправлено: {message}')
    except Exception as error:
        logging.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(current_timestamp):
    """Направляет запрос к API ЯндексПрактикума,возращает ответ."""
    params = {'from_date': current_timestamp}
    try:
        logging.info('Отправляю запрос к API ЯндексПрактикума')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if response.status_code != HTTPStatus.OK:
            logging.error('Недоступность эндпоинта')
            raise NotStatusOkException('Недоступность эндпоинта')
        return response.json()
    except ConnectionError:
        logging.error('Сбой при запросе к эндпоинту')
        raise ConnectionError('Сбой при запросе к эндпоинту')


def check_response(response):
    """Возвращает содержимое в ответе от ЯндексПрактикума."""
    if not isinstance(response, dict):
        logging.error('API передал не словарь')
        raise TypeError('API передал не словарь')
    homeworks = response.get('homeworks')
    if homeworks is None:
        logging.error('API не содержит ключа homeworks')
        raise KeyError('API не содержит ключа homeworks')
    if not isinstance(homeworks, list):
        logging.error('Содержимое не список')
        raise TypeError('Содержимое не список')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из ответа ЯндексПракутикум."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logging.error('В ответе API нет ключа homework_name')
        raise KeyError('В ответе API нет ключа homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        logging.error('В ответе API нет ключа homework_status')
        raise KeyError('В ответе API нет ключа homework_status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if verdict is None:
        logging.error('Неизвестный статус')
        raise KeyError('Неизвестный статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def parse_date(homework):
    """Извлекает дату обновления работы из ответа ЯндексПракутикум."""
    date_updated = homework.get('date_updated')
    if date_updated is None:
        logging.error('В ответе API нет ключа date_updated')
        raise KeyError('В ответе API нет ключа date_updated')
    return date_updated


def check_tokens():
    """Проверяет наличие токенов."""
    all([
        PRACTICUM_TOKEN is not None,
        TELEGRAM_TOKEN is not None,
        TELEGRAM_CHAT_ID is not None
    ])
    return all


def main():
    """Основная логика работы бота."""
    date_api_memory = None
    error_memory = None
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s - [%(levelname)s][%(lineno)s][%(filename)s]'
            '[%(funcName)s]- %(message)s'
        ),
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    if check_tokens():
        logging.info('Токены впорядке')
    else:
        logging.critical(
            'Не обнаружен один из ключей PRACTICUM_TOKEN,'
            'TELEGRAM_TOKEN, TELEGRAM_CHAT_ID'
        )
        raise NotTokenException(
            'Не обнаружен один из ключей PRACTICUM_TOKEN,'
            'TELEGRAM_TOKEN, TELEGRAM_CHAT_ID'
        )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            flag_message = 'Статус работы не изменился'
            if homeworks:
                message = parse_status(homeworks[0])
                date_updated = parse_date(homeworks[0])
                if str(date_updated) != str(date_api_memory):
                    date_api_memory = date_updated
                    flag_message = 'Статус работы изменился!!!'
                    send_message(bot, message)
            logging.info(flag_message)
            current_timestamp = int(time.time())
            error_memory = None
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if str(error) != str(error_memory):
                error_memory = error
                send_message(bot, message)
            current_timestamp = int(time.time())
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
