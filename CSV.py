import csv
import json


# Функция для преобразования CSV в JSON
def csv_to_json(csv_filename, json_filename):
    data_list = []

    # Открываем CSV файл
    with open(csv_filename, mode='r', encoding='utf-8') as csvfile:
        # Читаем CSV файл с учетом разделителя `;`
        csvreader = csv.reader(csvfile, delimiter=';')
        next(csvreader)  # Пропускаем заголовки

        for row in csvreader:
            # Убираем лишние пробелы и кавычки
            decision_number = row[0].strip().strip('"')
            data = row[1].strip().strip('"')

            # Создаем запись и добавляем её в список
            record = {
                "decision_number": decision_number,
                "data": data,
                "gender": ""  # Оставляем поле пустым
            }
            data_list.append(record)

    # Сохраняем в JSON файл
    with open(json_filename, mode='w', encoding='utf-8') as jsonfile:
        json.dump(data_list, jsonfile, ensure_ascii=False, indent=4)


# Укажите имена ваших файлов
csv_filename = 'input.csv'
json_filename = 'output.json'

# Преобразуем
csv_to_json(csv_filename, json_filename)
