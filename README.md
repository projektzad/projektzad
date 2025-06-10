# LDAP Admin - Aplikacja do Zarządzania Active Directory

Aplikacja webowa w technologii Flask do uproszczonego zarządzania użytkownikami i grupami w usłudze katalogowej Active Directory.

---

### Spis Treści
1.  [Kluczowe Funkcje](#kluczowe-funkcje)
2.  [Stos Technologiczny](#stos-technologiczny)
3.  [Zrzuty Ekranu](#zrzuty-ekranu)
4.  [Wymagania Wstępne](#wymagania-wstępne)
5.  [Instalacja](#instalacja)
6.  [Konfiguracja](#konfiguracja)
7.  [Użytkowanie](#użytkowanie)
8.  [Zatrzymywanie Aplikacji](#zatrzymywanie-aplikacji)
9.  [Licencja](#licencja)

---

### Kluczowe Funkcje

* **Zarządzanie Użytkownikami**: Dodawanie, usuwanie, blokowanie i odblokowywanie kont.
* **Zarządzanie Grupami**: Tworzenie, usuwanie oraz modyfikacja członkostwa w grupach.
* **Operacje Masowe**: Import użytkowników z plików `.csv` i `.xlsx` w celu ich dodania, zablokowania lub ustawienia daty wygaśnięcia.
* **Eksport Danych**: Eksport listy użytkowników do plików `.csv` i `.xlsx`.
* **Bezpieczeństwo**: Logowanie do serwera LDAP przy użyciu dedykowanego konta i zarządzanie sesją.
* **Personalizacja**: Możliwość konfiguracji domyślnych wartości (np. jednostka organizacyjna, menedżer) dla nowo tworzonych użytkowników oraz atrybutów wyświetlanych w tabeli.

### Stos Technologiczny

* **Backend**: Python, Flask, Gunicorn
* **Komunikacja z AD**: ldap3
* **Frontend**: HTML, CSS, JavaScript
* **Obsługa plików Excel**: openpyxl


### Wymagania Wstępne

* System operacyjny oparty na Linuksie
* Python 3.x
* `pip` (manager pakietów Pythona)
* Dostęp do serwera Active Directory z kontem uprawnionym do wprowadzania zmian.

### Instalacja

Projekt zawiera skrypt `install.sh`, który automatyzuje cały proces.

1.  Sklonuj repozytorium na swój serwer.
2.  Nadaj uprawnienia do wykonania dla skryptu:
    ```bash
    chmod +x install.sh
    ```
3.  Uruchom skrypt instalacyjny:
    ```bash
    ./install.sh
    ```
Skrypt zainstaluje wszystkie zależności z pliku `myapp/requirements.txt` i uruchomi aplikację na serwerze Gunicorn. Aplikacja będzie dostępna na porcie **5000**.

### Konfiguracja

Przed pierwszym użyciem aplikacji, należy dostosować jej konfigurację do własnego środowiska Active Directory.

1.  **Domyślne wartości dla użytkowników**: Edytuj plik `myapp/app/config/user_defaults.json`, aby ustawić domyślne ścieżki (DN) dla jednostek organizacyjnych (OU), menedżera oraz grup.
2.  **Ustawienia w interfejsie**: Po zalogowaniu, przejdź do zakładki "Ustawienia" (Settings), aby skonfigurować atrybuty, które mają być wyświetlane w tabeli użytkowników.

### Użytkowanie

1.  Otwórz przeglądarkę i wejdź na adres `http://<adres_ip_serwera>:5000`.
2.  Zaloguj się, używając swoich danych uwierzytelniających do Active Directory.
3.  Po zalogowaniu uzyskasz dostęp do głównego panelu, gdzie możesz zarządzać użytkownikami i grupami.

### Zatrzymywanie Aplikacji

Aby zatrzymać aplikację działającą w tle, użyj skryptu `stop.sh`.

1.  Nadaj uprawnienia do wykonania:
    ```bash
    chmod +x stop.sh
    ```
2.  Uruchom skrypt:
    ```bash
    ./stop.sh
    ```

### Licencja

Ten projekt jest udostępniany na licencji [MIT](LICENSE).

# LDAP Admin - Active Directory Management Tool

A Flask-based web application for simplified user and group management in an Active Directory service.

---

### Table of Contents
1.  [Key Features](#key-features)
2.  [Technology Stack](#technology-stack)
3.  [Screenshots](#screenshots)
4.  [Prerequisites](#prerequisites)
5.  [Installation](#installation)
6.  [Configuration](#configuration)
7.  [Usage](#usage)
8.  [Stopping the Application](#stopping-the-application)
9.  [License](#license)

---

### Key Features

* **User Management**: Add, delete, block, and unblock user accounts.
* **Group Management**: Create, delete, and modify group membership.
* **Bulk Operations**: Import users from `.csv` and `.xlsx` files to add them, block them, or set their expiration dates.
* **Data Export**: Export the user list to `.csv` and `.xlsx` files.
* **Security**: Log in to the LDAP server using a dedicated account and manage the session securely.
* **Customization**: Ability to configure default values (e.g., organizational unit, manager) for new users and customize the attributes displayed in the user table.

### Technology Stack

* **Backend**: Python, Flask, Gunicorn
* **AD Communication**: ldap3
* **Frontend**: HTML, CSS, JavaScript
* **Excel File Handling**: openpyxl

### Prerequisites

* A Linux-based operating system
* Python 3.x
* `pip` (Python package manager)
* Access to an Active Directory server with an account authorized to make changes.

### Installation

The project includes an `install.sh` script that automates the entire process.

1.  Clone the repository to your server.
2.  Grant execution permissions to the script:
    ```bash
    chmod +x install.sh
    ```
3.  Run the installation script:
    ```bash
    ./install.sh
    ```
The script will install all dependencies from the `myapp/requirements.txt` file and start the application on a Gunicorn server. The application will be available on port **5000**.

### Configuration

Before using the application for the first time, you need to adjust its configuration to your Active Directory environment.

1.  **Default User Values**: Edit the `myapp/app/config/user_defaults.json` file to set the default Distinguished Names (DNs) for organizational units (OUs), managers, and groups.
2.  **In-App Settings**: After logging in, navigate to the "Settings" tab to configure which attributes should be displayed in the user table.

### Usage

1.  Open your browser and go to `http://<your_server_ip>:5000`.
2.  Log in using your Active Directory credentials.
3.  After logging in, you will have access to the main dashboard where you can manage users and groups.

### Stopping the Application

To stop the application running in the background, use the `stop.sh` script.

1.  Grant execution permissions:
    ```bash
    chmod +x stop.sh
    ```
2.  Run the script:
    ```bash
    ./stop.sh
    ```

### License

This project is licensed under the [MIT](LICENSE) License.