from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
import os
import time

load_dotenv()
driver_path = os.getenv('DRIVER_PATH')
url = os.getenv('TEST_URL')
screenshot_dir = os.getenv('SCREENSHOTS_DIR')

os.makedirs(screenshot_dir, exist_ok=True)

STAR_RATINGS_TO_CHECK = [3]  # Проверяемые рейтинги

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
    """Улучшенное ожидание загрузки отелей"""
    try:
        # Ждем исчезновения прелоадера (если есть)
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, ".placeholder-preloader--active")))
        except:
            pass
        
        # Дополнительные проверки для уверенности в загрузке
        WebDriverWait(driver, 20).until(lambda d: 
            d.execute_script("""
                // Проверяем что нет активных AJAX-запросов
                if (window.jQuery) {
                    return jQuery.active === 0;
                }
                return true;
            """)
        )
        
        # Ждем появления хотя бы одной карточки отеля
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")))
        
        # Дополнительная проверка что карточки видимы
        WebDriverWait(driver, 10).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")))
        
        print("Отели успешно загружены")
    except Exception as e:
        print("Ошибка загрузки отелей:", e)
        take_screenshot(driver, "hotels_load_error")
        raise

def apply_star_filter(driver, star_rating):
    """Применение фильтра по звёздам"""
    try:
        checkbox_xpath = f"//div[@id='ch-hotels-stars']//input[@value='{star_rating}']"
        checkbox = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, checkbox_xpath)))
        
        label = checkbox.find_element(By.XPATH, "./following-sibling::span[@class='name']")
        
        is_checked = checkbox.is_selected()
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", label)
        
        WebDriverWait(driver, 10).until(
            lambda d: checkbox.is_selected() != is_checked)
        
        print(f"Фильтр {star_rating} звёзд {'применён' if not is_checked else 'снят'}")
        wait_for_hotels(driver)
        
    except Exception as e:
        print(f"Ошибка работы с фильтром {star_rating} звёзд:", e)
        take_screenshot(driver, f"star_filter_{star_rating}_error")
        raise

def check_star_ratings(driver, expected_stars):
    """Проверка соответствия рейтингов отелей"""
    try:
        # Дополнительное ожидание перед проверкой
        time.sleep(1)  # Небольшая пауза для стабилизации
        
        hotels = driver.find_elements(By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")
        wrong_ratings = []
        
        for hotel in hotels:
            try:
                stars_div = WebDriverWait(hotel, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".stars[class*='stars-rating-']")))
                
                star_class = [c for c in stars_div.get_attribute("class").split() 
                            if c.startswith('stars-rating-')][0]
                actual_stars = int(star_class.split('-')[-1])
                
                if actual_stars != expected_stars:
                    name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                    wrong_ratings.append(f"{name} (ожидалось {expected_stars}, получили {actual_stars})")
            except Exception as e:
                print(f"Ошибка при проверке отеля: {e}")
                continue
        
        if wrong_ratings:
            print(f"Найдено {len(wrong_ratings)} отелей с неверным рейтингом:")
            for error in wrong_ratings[:3]:
                print(f" - {error}")
            if len(wrong_ratings) > 3:
                print(f" - и ещё {len(wrong_ratings)-3} отелей...")
            
            take_screenshot(driver, f"wrong_stars_{expected_stars}")
            raise AssertionError(f"Найдены отели с несоответствующим рейтингом ({expected_stars} звёзд)")
        
        if len(hotels) == 0:
            raise AssertionError("После фильтрации не найдено ни одного отеля")
            
        print(f"✓ Все {len(hotels)} отелей соответствуют {expected_stars} звёздам")
        return len(hotels)
        
    except Exception as e:
        print("Ошибка проверки рейтинга:", e)
        take_screenshot(driver, "rating_check_error")
        raise

def process_pagination(driver, expected_stars):
    """Обработка пагинации с учетом всех возможных состояний"""
    total_hotels = 0
    processed_pages = 0
    
    while True:
        # Проверяем отели на текущей странице
        hotels_count = check_star_ratings(driver, expected_stars)
        total_hotels += hotels_count
        processed_pages += 1
        
        # Проверяем состояние пагинации
        try:
            # Ищем кнопку "Далее" в любом состоянии
            next_buttons = driver.find_elements(By.CSS_SELECTOR, ".pagination .next")
            
            if not next_buttons:
                print("\nКнопка 'Далее' не найдена - конец пагинации")
                break
                
            next_button = next_buttons[0]
            
            # Проверяем два варианта неактивной кнопки "Далее"
            if ("disabled" in next_button.get_attribute("class") or 
                "current" in next_button.get_attribute("class")):
                print("\nДостигнут конец пагинации (неактивная кнопка 'Далее')")
                break
                
            print(f"\nПереходим на страницу {processed_pages + 1}...")
            
            # Прокручиваем и кликаем с использованием JavaScript
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", next_button)
            
            # Ждем полной загрузки новой страницы
            wait_for_hotels(driver)
            time.sleep(1)  # Дополнительная пауза для стабилизации
            
        except Exception as e:
            print(f"Ошибка при обработке пагинации: {e}")
            take_screenshot(driver, "pagination_error")
            break
    
    print(f"\nИтого проверено: {processed_pages} страниц, {total_hotels} отелей")
    return total_hotels

def test_star_filter(driver, star_rating):
    """Полный тест для одного фильтра"""
    print(f"\n=== Начинаем тестирование фильтра {star_rating} звёзд ===")
    
    # Применяем фильтр
    apply_star_filter(driver, star_rating)
    
    # Проверяем все страницы пагинации
    try:
        total_hotels = process_pagination(driver, star_rating)
        
        if total_hotels == 0:
            raise AssertionError(f"После фильтрации {star_rating} звёзд не найдено ни одного отеля")
        
    finally:
        # Всегда снимаем фильтр, даже если были ошибки
        print("\nСнимаем фильтр...")
        apply_star_filter(driver, star_rating)
        time.sleep(1)

def main():
    driver = None
    try:
        driver = setup_driver()
        driver.get(url)
        time.sleep(2)
        wait_for_hotels(driver)
        
        for stars in STAR_RATINGS_TO_CHECK:
            test_star_filter(driver, stars)
        
        print("\nВсе тесты успешно пройдены!")
        
    except Exception as e:
        print("\nТестирование завершено с ошибками:", e)
        take_screenshot(driver, "test_failure")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()