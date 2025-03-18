document.addEventListener('DOMContentLoaded', function () {
    // Obsługa rozwijania/zamykania atrybutów użytkownika dla obu tabel
    document.querySelectorAll('.toggle-attributes').forEach(button => {
        button.addEventListener('click', function () {
            let target = document.querySelector(button.getAttribute('data-target'));
            target.classList.toggle('collapse');
            button.textContent = target.classList.contains('collapse') ? 'Show Attributes' : 'Hide Attributes';
        });
    });

    // Obsługa sortowania dla obu tabel
    ['userTable', 'userTable2'].forEach(tableId => {
        const table = document.getElementById(tableId);
        if (!table) return;

        const headers = table.querySelectorAll("thead th");
        headers.forEach((header, index) => {
            header.addEventListener("click", () => {
                sortTable(tableId, index);
            });
        });
    });

    // Obsługa filtrowania dla obu tabel
    document.getElementById('searchUser').addEventListener('input', function () {
        filterTable('userTable', this.value.toLowerCase());
    });

    document.getElementById('searchRemove').addEventListener('input', function () {
        filterTable('userTable2', this.value.toLowerCase());
    });

    // Obsługa zaznaczania wszystkich checkboxów dla obu tabel
    setupSelectAll('selectAll', 'userTable', 'add_users');
    setupSelectAll('selectAll2', 'userTable2', 'remove_users');
});

// Funkcja filtrowania tabeli
function filterTable(tableId, inputValue) {
    let rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach(row => {
        let cells = row.querySelectorAll('td');
        let match = false;

        // Sprawdzanie każdej komórki wiersza
        cells.forEach(cell => {
            if (cell.textContent.toLowerCase().includes(inputValue)) {
                match = true;
            }
        });

        row.style.display = match ? '' : 'none';
    });
}

// Funkcja sortująca dla dowolnej tabeli
function sortTable(tableId, columnIndex) {
    let table = document.getElementById(tableId);
    let rows = Array.from(table.querySelectorAll("tbody tr"));
    let ascending = table.dataset.sortOrder !== "asc";

    rows.sort((rowA, rowB) => {
        let cellA = rowA.getElementsByTagName("td")[columnIndex]?.textContent.trim().toLowerCase();
        let cellB = rowB.getElementsByTagName("td")[columnIndex]?.textContent.trim().toLowerCase();
        
        if (cellA < cellB) return ascending ? -1 : 1;
        if (cellA > cellB) return ascending ? 1 : -1;
        return 0;
    });

    // Wyczyść tabelę i dodaj posortowane wiersze
    let tbody = table.querySelector("tbody");
    tbody.innerHTML = "";
    rows.forEach(row => tbody.appendChild(row));

    // Zaktualizuj kolejność sortowania
    table.dataset.sortOrder = ascending ? "asc" : "desc";
    updateSortIcons(tableId, columnIndex, ascending);
}

// Aktualizacja ikonki sortowania w nagłówku dla danej tabeli
function updateSortIcons(tableId, columnIndex, ascending) {
    let headers = document.querySelectorAll(`#${tableId} th`);
    headers.forEach((header, index) => {
        header.textContent = header.textContent.replace(/⬆|⬇/, ''); // Usuń poprzednie ikony
        if (index === columnIndex) {
            header.textContent += ascending ? ' ⬆' : ' ⬇'; // Dodaj nową ikonę
        }
    });
}

// Funkcja obsługująca "Zaznacz/Wszystko" dla dowolnej tabeli
function setupSelectAll(selectAllId, tableId, inputName) {
    const selectAllCheckbox = document.getElementById(selectAllId);
    const userCheckboxes = document.querySelectorAll(`#${tableId} input[name="${inputName}"]`);

    selectAllCheckbox.addEventListener('change', function () {
        userCheckboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
    });

    // Sprawdź, czy wszystkie checkboxy są zaznaczone, aby ustawić stan "Select All"
    userCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const allChecked = Array.from(userCheckboxes).every(checkbox => checkbox.checked);
            selectAllCheckbox.checked = allChecked;
        });
    });
}
