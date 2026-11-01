
import requests
import uuid

BASE_URL = "http://localhost:8000"
REGISTER_URL = f"{BASE_URL}//api/v1/auth/register"

# Если в проекте подключён префикс /api/v1,
# используйте:
# REGISTER_URL = f"{BASE_URL}/api/v1/auth/register"

session = requests.Session()

print("Проверка API...")

try:
    response = session.get(f"{BASE_URL}/openapi.json", timeout=5)
    response.raise_for_status()
    print("API доступен")
except requests.RequestException as exc:
    print(f"API недоступен: {exc}")
    raise SystemExit(1)

print("\nРегистрация пользователей")

for i in range(5):
    data = {
        "phone": f"+1999{uuid.uuid4().int % 10**10:010d}",
        "password": "TestPassword123",
        "role": "CUSTOMER",
    }

    try:
        response = session.post(
            REGISTER_URL,
            json=data,
            timeout=10,
        )

        print(f"\nПользователь {i + 1}")
        print(f"Телефон: {data['phone']}")
        print(f"HTTP: {response.status_code}")

        if response.ok:
            result = response.json()
            print(f"ID: {result.get('user_id')}")
            print(f"Роль: {result.get('role')}")
            print("Регистрация успешна")
        else:
            print(f"Ошибка: {response.text}")

    except requests.RequestException as exc:
        print(f"Ошибка запроса: {exc}")
