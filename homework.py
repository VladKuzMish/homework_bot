import json
import os
import time
import requests
import sys

import telegram
import logging
from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import NotStatusOkException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
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
    except json.JSONDecodeError:
        logging.error('Ошибка при преобразовании')
        raise json.JSONDecodeError('Ошибка при преобразовании')


def check_response(response):
    """Возвращает содержимое в ответе от ЯндексПрактикума."""
    if not isinstance(response, dict):
        logging.error('API передал не словарь')
        raise TypeError('API передал не словарь')
    if response.get('homeworks') is None:
        logging.error('Ошибка ключа homeworks или response')
        raise TypeError('Ошибка ключа homeworks или response')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        logging.error('Содержимое не список')
        raise TypeError('Содержимое не список')
    return homework


def parse_status(homework):
    """Извлекает статус работы из ответа ЯндексПракутикум."""
    homework_name = homework.get('homework_name')
    if homework_name('homework_name') is None:
        logging.error('В ответе API нет ключа homework_name')
        raise KeyError('В ответе API нет ключа homework_name')
    homework_status = homework.get('status')
    if homework_status('status') is None:
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
    tocens_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует обязательная переменная окружения:')
    tokens_bool = True
    for i in tocens_list:
        if i is None:
            tokens_bool = True
            logging.critical({no_tokens_msg})
        return tokens_bool


def main():
    """Основная логика работы бота."""
    error_memory = ('')
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s - [%(levelname)s][%(lineno)s][%(filename)s]'
            '[%(funcName)s]- %(message)s'
        ),
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    tmp_status = 'reviewing'
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logging.info(
                'Изменений нет, ждем 10 минут и проверяем API')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if str(error) != str(error_memory):
                error_memory = error
                send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
