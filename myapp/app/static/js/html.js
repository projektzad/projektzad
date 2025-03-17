
// Obsługa rozwijania/zamykania atrybutów użytkownika
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.toggle-attributes').forEach(button => {
        button.addEventListener('click', function () {
            let target = document.querySelector(button.getAttribute('data-target'));
            target.classList.toggle('collapse');
            button.textContent = target.classList.contains('collapse') ? 'Show Attributes' : 'Hide Attributes';
        });
    });

    // Dodanie event listenerów do nagłówków tabeli
    const table = document.getElementById("userTable");
    const headers = table.querySelectorAll("thead th");

    headers.forEach((header, index) => {
        header.addEventListener("click", () => {
            sortTable(index); // Wywołaj funkcję sortTable z indeksem kolumny
        });
    });
});

// Filtrowanie tabeli użytkowników
document.getElementById('searchUser').addEventListener('keyup', function () {
    let input = this.value.toLowerCase();
    let rows = document.querySelectorAll('#userTable tbody tr');

    rows.forEach(row => {
        let text = row.innerText.toLowerCase();
        row.style.display = text.includes(input) ? '' : 'none';
    });
});

// Funkcja sortująca tabelę
function sortTable(columnIndex) {
    let table = document.getElementById("userTable");
    let rows = Array.from(table.getElementsByTagName("tr")).slice(1);
    let ascending = table.dataset.sortOrder !== "asc";

    rows.sort((rowA, rowB) => {
        let cellA = rowA.getElementsByTagName("td")[columnIndex]?.textContent.trim().toLowerCase();
        let cellB = rowB.getElementsByTagName("td")[columnIndex]?.textContent.trim().toLowerCase();
        
        if (cellA < cellB) return ascending ? -1 : 1;
        if (cellA > cellB) return ascending ? 1 : -1;
        return 0;
    });

    // Wyczyść tabelę i dodaj posortowane wiersze
    while (table.rows.length > 1) {
        table.deleteRow(1);
    }
    rows.forEach(row => table.appendChild(row));

    // Zaktualizuj kolejność sortowania
    table.dataset.sortOrder = ascending ? "asc" : "desc";
    updateSortIcons(columnIndex, ascending);
}


// Aktualizacja ikonki sortowania w nagłówku
function updateSortIcons(columnIndex, ascending) {
    let headers = document.querySelectorAll("#userTable th");
    headers.forEach((header, index) => {
        header.textContent = header.textContent.replace(/⬆|⬇/, ''); // Usuń poprzednie ikony
        if (index === columnIndex) {
            header.textContent += ascending ? ' ⬆' : ' ⬇'; // Dodaj nową ikonę
        }
    });
}
const selectAllCheckbox = document.getElementById("selectAll");
const userCheckboxes = document.querySelectorAll('input[name="selected_users"]');

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
