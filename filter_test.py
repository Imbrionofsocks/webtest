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

STAR_RATINGS_TO_CHECK = [5, 4, 3]  # Проверяемые рейтинги

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
    """Ожидание загрузки отелей по исчезновению прелоадера"""
    try:
        # Сначала дожидаемся появления прелоадера (если он есть)
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".placeholder-preloader--active")))
            print("Обнаружен прелоадер, ожидаем загрузки...")
        except:
            print("Прелоадер не найден, продолжаем")
        
        # Затем ждём исчезновения прелоадера
        WebDriverWait(driver, 20).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".placeholder-preloader--active")))
        
        # Дополнительно проверяем, что появились карточки отелей
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")))
        
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
        
        # Ждём изменения состояния чекбокса
        WebDriverWait(driver, 10).until(
            lambda d: checkbox.is_selected() != is_checked)
        
        print(f"Фильтр {star_rating} звёзд {'применён' if not is_checked else 'снят'}")
        
        # Ждём завершения загрузки после применения фильтра
        wait_for_hotels(driver)
        
    except Exception as e:
        print(f"Ошибка работы с фильтром {star_rating} звёзд:", e)
        take_screenshot(driver, f"star_filter_{star_rating}_error")
        raise

def check_star_ratings(driver, expected_stars):
    """Проверка соответствия рейтингов отелей"""
    try:
        hotels = driver.find_elements(By.CSS_SELECTOR, "li.item[itemtype='https://schema.org/Hotel']")
        wrong_ratings = []
        
        for hotel in hotels:
            try:
                stars_div = hotel.find_element(By.CSS_SELECTOR, ".stars[class*='stars-rating-']")
                star_class = [c for c in stars_div.get_attribute("class").split() if c.startswith('stars-rating-')][0]
                actual_stars = int(star_class.split('-')[-1])
                
                if actual_stars != expected_stars:
                    name = hotel.find_element(By.CSS_SELECTOR, "[itemprop='name']").text.strip()
                    wrong_ratings.append(f"{name} (ожидалось {expected_stars}, получили {actual_stars})")
            except Exception as e:
                print(f"Ошибка при проверке отеля: {e}")
                continue
        
        if wrong_ratings:
            print(f"❌ Найдено {len(wrong_ratings)} отелей с неверным рейтингом:")
            for error in wrong_ratings[:3]:
                print(f" - {error}")
            if len(wrong_ratings) > 3:
                print(f" - и ещё {len(wrong_ratings)-3} отелей...")
            
            take_screenshot(driver, f"wrong_stars_{expected_stars}")
            raise AssertionError(f"Найдены отели с несоответствующим рейтингом ({expected_stars} звёзд)")
        
        if len(hotels) == 0:
            raise AssertionError("После фильтрации не найдено ни одного отеля")
            
        print(f"✓ Все {len(hotels)} отелей соответствуют {expected_stars} звёздам")
        
    except Exception as e:
        print("Ошибка проверки рейтинга:", e)
        take_screenshot(driver, "rating_check_error")
        raise

def main():
    driver = None
    try:
        driver = setup_driver()
        driver.get(url)
        time.sleep(2)
        
        # Первоначальная загрузка отелей
        wait_for_hotels(driver)
        
        for stars in STAR_RATINGS_TO_CHECK:
            print(f"\n=== Тестируем фильтр {stars} звёзд ===")
            
            apply_star_filter(driver, stars)
            check_star_ratings(driver, stars)
            apply_star_filter(driver, stars)  # Снимаем фильтр
            time.sleep(1)
        
        print("\nВсе тесты успешно пройдены!")
        
    except Exception as e:
        print("\nТестирование завершено с ошибками:", e)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()