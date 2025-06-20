from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
import os
import time
from enum import Enum

load_dotenv()
driver_path = os.getenv('DRIVER_PATH')
url = os.getenv('TEST_URL')
screenshot_dir = os.getenv('SCREENSHOTS_DIR')

os.makedirs(screenshot_dir, exist_ok=True)

class TestMode(Enum):
    SINGLE = 1
    COMBINED = 2
    ALL = 3
    CUSTOM = 4

TEST_CONFIG = {
    'modes': {
        TestMode.SINGLE: {
            'description': 'Проверка каждого фильтра по отдельности',
            'star_combinations': [[5], [4], [3], [2], [1], [0]]
        },
        TestMode.COMBINED: {
            'description': 'Проверка основных комбинаций',
            'star_combinations': [
                [5, 4], 
                [4, 3], 
                [3, 2], 
                [5, 3, 1],
                [4, 2, 0]
            ]
        },
        TestMode.ALL: {
            'description': 'Проверка всех возможных комбинаций',
            'star_combinations': [
                [5, 4, 3, 2, 1, 0],
                [5, 4, 3],
                [4, 3, 2],
                [3, 2, 1],
                [2, 1, 0],
                [5, 3, 1],
                [4, 2, 0]
            ]
        },
        TestMode.CUSTOM: {
            'description': 'Свой набор комбинаций',
            'star_combinations': []
        }
    }
}

def show_menu():
    """Отображает меню выбора режима тестирования"""
    print("\n" + "="*50)
    print("Выберите режим тестирования:")
    for mode in TestMode:
        if mode != TestMode.CUSTOM:  # Custom обрабатываем отдельно
            print(f"{mode.value}. {TEST_CONFIG['modes'][mode]['description']}")
    print(f"{TestMode.CUSTOM.value}. Задать свои комбинации фильтров")
    print("0. Выход")
    
    while True:
        try:
            choice = int(input("Ваш выбор: "))
            if 0 <= choice <= len(TestMode):
                return choice
            print("Пожалуйста, введите число от 0 до", len(TestMode))
        except ValueError:
            print("Пожалуйста, введите число")

def get_custom_combinations():
    """Запрашивает пользовательские комбинации фильтров"""
    print("\n" + "="*50)
    print("Введите комбинации звёзд для проверки (например: 5,4 или 3,2,1)")
    print("Оставьте пустую строку для завершения ввода")
    
    combinations = []
    while True:
        input_str = input("Комбинация: ").strip()
        if not input_str:
            break
            
        try:
            stars = list(map(int, input_str.split(',')))
            combinations.append(stars)
            print(f"Добавлена комбинация: {stars}")
        except:
            print("Ошибка формата. Используйте числа через запятую (например: 5,4)")
    
    if not combinations:
        print("Не добавлено ни одной комбинации. Будет использован режим по умолчанию")
        return None
    
    return combinations

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=options)

def take_screenshot(driver, filename):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(screenshot_dir, f"{filename}_{timestamp}.png")
    driver.save_screenshot(screenshot_path)
    print(f"Скриншот сохранён: {screenshot_path}")

def wait_for_hotels(driver):
    try:
        WebDriverWait(driver, 20).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".placeholder-preloader--active")))
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")))
        print("Отели успешно загружены")
    except Exception as e:
        print("Ошибка загрузки отелей:", e)
        take_screenshot(driver, "hotels_load_error")
        raise

def apply_star_filters(driver, star_ratings):
    try:
        # Снимаем все фильтры звёзд
        star_checkboxes = driver.find_elements(By.CSS_SELECTOR, "#ch-hotels-stars input[type='checkbox']")
        for checkbox in star_checkboxes:
            if checkbox.is_selected():
                label = checkbox.find_element(By.XPATH, "./following-sibling::span[@class='name']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", label)
                time.sleep(0.2)
        
        # Применяем нужные фильтры
        for rating in star_ratings:
            checkbox_xpath = f"//div[@id='ch-hotels-stars']//input[@value='{rating}']"
            checkbox = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, checkbox_xpath)))
            
            label = checkbox.find_element(By.XPATH, "./following-sibling::span[@class='name']")
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", label)
            time.sleep(0.3)
        
        print(f"Применены фильтры: {', '.join(map(str, star_ratings))} звёзд")
        wait_for_hotels(driver)
        
    except Exception as e:
        print(f"Ошибка применения фильтров {star_ratings}:", e)
        take_screenshot(driver, f"filter_apply_error_{'_'.join(map(str, star_ratings))}")
        raise

def check_star_ratings(driver, expected_ratings):
    try:
        time.sleep(1)
        hotels = driver.find_elements(By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")
        wrong_ratings = []
        
        for hotel in hotels:
            try:
                # Ищем элементы с рейтингом звёзд
                star_elements = hotel.find_elements(By.CSS_SELECTOR, ".stars[class*='stars-rating-']")
                
                if 0 in expected_ratings:
                    # Если в фильтре есть "Без звёзд", возможны два варианта:
                    # 1. Отель без звёзд (нет элементов рейтинга)
                    # 2. Отель с рейтингом из разрешенных в фильтре
                    if star_elements:
                        star_class = [c for c in star_elements[0].get_attribute("class").split() 
                                    if c.startswith('stars-rating-')][0]
                        actual_stars = int(star_class.split('-')[-1])
                        
                        # Проверяем, что рейтинг есть в ожидаемых (кроме 0)
                        if actual_stars not in [x for x in expected_ratings if x != 0]:
                            name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                            expected_str = "Без звёзд или " + ', '.join(map(str, [x for x in expected_ratings if x != 0]))
                            wrong_ratings.append(f"{name} (допустимы: {expected_str}, получили: {actual_stars})")
                else:
                    # Если фильтр не содержит "Без звёзд", проверяем обязательное наличие рейтинга
                    if not star_elements:
                        name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                        wrong_ratings.append(f"{name} (не найден рейтинг звёзд)")
                        continue
                        
                    star_class = [c for c in star_elements[0].get_attribute("class").split() 
                                if c.startswith('stars-rating-')][0]
                    actual_stars = int(star_class.split('-')[-1])
                    
                    if actual_stars not in expected_ratings:
                        name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                        wrong_ratings.append(f"{name} (допустимы: {', '.join(map(str, expected_ratings))}, получили: {actual_stars})")
                        
            except Exception as e:
                print(f"Ошибка при проверке отеля: {e}")
                name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                wrong_ratings.append(f"{name} (ошибка проверки)")
                continue
        
        if wrong_ratings:
            print(f"Найдено {len(wrong_ratings)} отелей с неверным рейтингом:")
            for error in wrong_ratings[:3]:
                print(f" - {error}")
            if len(wrong_ratings) > 3:
                print(f" - и ещё {len(wrong_ratings)-3} отелей...")
            
            take_screenshot(driver, f"wrong_stars_{'_'.join(map(str, expected_ratings))}")
            raise AssertionError(f"Найдены отели с недопустимым рейтингом ({expected_ratings} звёзд)")
        
        if len(hotels) == 0:
            raise AssertionError("После фильтрации не найдено ни одного отеля")
            
        # Формируем читаемое описание фильтра
        if 0 in expected_ratings:
            other_ratings = [x for x in expected_ratings if x != 0]
            if other_ratings:
                expected_str = f"Без звёзд или {', '.join(map(str, other_ratings))}"
            else:
                expected_str = "Без звёзд"
        else:
            expected_str = ', '.join(map(str, expected_ratings))
            
        print(f"✓ Все {len(hotels)} отелей соответствуют фильтру ({expected_str})")
        return len(hotels)
        
    except Exception as e:
        print("Ошибка проверки рейтинга:", e)
        take_screenshot(driver, "rating_check_error")
        raise


def process_pagination(driver, expected_ratings):
    total_hotels = 0
    processed_pages = 0
    
    while True:
        hotels_count = check_star_ratings(driver, expected_ratings)
        total_hotels += hotels_count
        processed_pages += 1
        
        try:
            next_buttons = driver.find_elements(By.CSS_SELECTOR, ".pagination .next")
            
            if not next_buttons:
                print("\nКнопка 'Далее' не найдена - конец пагинации")
                break
                
            next_button = next_buttons[0]
            
            if ("disabled" in next_button.get_attribute("class") or 
                "current" in next_button.get_attribute("class")):
                print("\nДостигнут конец пагинации")
                break
                
            print(f"\nПереходим на страницу {processed_pages + 1}...")
            driver.execute_script("arguments[0].scrollIntoView();", next_button)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", next_button)
            wait_for_hotels(driver)
            time.sleep(1)
            
        except Exception as e:
            print(f"Ошибка пагинации: {e}")
            take_screenshot(driver, "pagination_error")
            break
    
    print(f"\nИтого проверено: {processed_pages} страниц, {total_hotels} отелей")
    return total_hotels

def run_test_mode(driver, mode, custom_combinations=None):
    print(f"\n=== Режим тестирования: {TEST_CONFIG['modes'][mode]['description']} ===")
    
    combinations = custom_combinations if mode == TestMode.CUSTOM else TEST_CONFIG['modes'][mode]['star_combinations']
    
    for combination in combinations:
        print(f"\nТестируем комбинацию: {combination} звёзд")
        
        try:
            apply_star_filters(driver, combination)
            total_hotels = process_pagination(driver, combination)
            
            if total_hotels == 0:
                print(f"Предупреждение: для комбинации {combination} не найдено отелей")
            
        finally:
            print("\nСнимаем фильтры...")
            star_checkboxes = driver.find_elements(By.CSS_SELECTOR, "#ch-hotels-stars input[type='checkbox']:checked")
            for checkbox in star_checkboxes:
                label = checkbox.find_element(By.XPATH, "./following-sibling::span[@class='name']")
                driver.execute_script("arguments[0].click();", label)
            time.sleep(1)

def main():
    driver = None
    try:
        # Выбор режима тестирования
        choice = show_menu()
        if choice == 0:
            print("Выход из программы")
            return
            
        selected_mode = TestMode(choice)
        
        # Обработка custom режима
        custom_combinations = None
        if selected_mode == TestMode.CUSTOM:
            custom_combinations = get_custom_combinations()
            if not custom_combinations:
                selected_mode = TestMode.SINGLE  # Fallback на режим по умолчанию
        
        # Запуск тестов
        driver = setup_driver()
        driver.get(url)
        time.sleep(2)
        wait_for_hotels(driver)
        
        run_test_mode(driver, selected_mode, custom_combinations)
        
        print("\nВсе тесты успешно пройдены!")
        
    except Exception as e:
        print("\nТестирование завершено с ошибками:", e)
        take_screenshot(driver, "test_failure")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()