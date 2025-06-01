// app/static/js/theme.js
document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const moonIcon = document.getElementById('theme-icon-moon');
    const sunIcon = document.getElementById('theme-icon-sun');

    let currentTheme = localStorage.getItem('theme') || 'light';

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (theme === 'dark') {
            if (moonIcon) moonIcon.style.display = 'none';
            if (sunIcon) sunIcon.style.display = 'inline';
        } else {
            if (moonIcon) moonIcon.style.display = 'inline';
            if (sunIcon) sunIcon.style.display = 'none';
        }
    }

    applyTheme(currentTheme); // Apply initial theme

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            let theme = document.documentElement.getAttribute('data-theme');
            if (theme === 'dark') {
                currentTheme = 'light';
            } else {
                currentTheme = 'dark';
            }
            localStorage.setItem('theme', currentTheme);
            applyTheme(currentTheme);
        });
    }
});