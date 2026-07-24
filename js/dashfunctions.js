// ==========================================================================
// File: js/filters.js (Complete Frontend Navigation & Calendar Framework)
// ==========================================================================
let tabVisibilityCriteria = { 'tab1': false, 'tab2': false, 'tab3': false };

function checkSecureSessionAuthentication() {
    const roleContainer = document.querySelector('.tab-buttons');
    tabVisibilityCriteria = { 'tab1': false, 'tab2': false, 'tab3': false };

    if (roleContainer) {
        const allowStudent = roleContainer.getAttribute('data-student') === 'true';
        const allowFaculty = roleContainer.getAttribute('data-faculty') === 'true';
        const allowProctor = roleContainer.getAttribute('data-proctor') === 'true';

        if (allowStudent) tabVisibilityCriteria['tab1'] = true;
        if (allowFaculty) tabVisibilityCriteria['tab2'] = true;
        if (allowProctor) tabVisibilityCriteria['tab3'] = true;
    }
    setupAccessibleTabs();
}

function setupAccessibleTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    let firstVisibleTabBtn = null;

    for (const [tabId, isVisible] of Object.entries(tabVisibilityCriteria)) {
        const targetButton = document.getElementById(`btn-${tabId}`);
        if (targetButton) {
            if (isVisible) {
                targetButton.classList.remove('hidden');
                if (!firstVisibleTabBtn) firstVisibleTabBtn = targetButton;
            } else {
                targetButton.classList.add('hidden');
            }
        }
    }
    if (firstVisibleTabBtn) activateTab(firstVisibleTabBtn);

    tabs.forEach(tab => {
        tab.addEventListener('click', e => { activateTab(e.currentTarget); });
    });
}

function activateTab(targetTab) {
    const tabContainer = targetTab.closest('.tab-container');
    tabContainer.querySelectorAll('.tab-btn').forEach(btn => {
        btn.setAttribute('aria-selected', 'false'); btn.setAttribute('tabindex', '-1');
    });
    targetTab.setAttribute('aria-selected', 'true'); targetTab.setAttribute('tabindex', '0');

    tabContainer.querySelectorAll('.tab-content').forEach(panel => panel.setAttribute('aria-hidden', 'true'));
    const targetPanel = document.getElementById(targetTab.getAttribute('aria-controls'));
    if (targetPanel) targetPanel.setAttribute('aria-hidden', 'false');
}

function applyMeetingDaysClamping() {
    const courseDropdown = document.getElementById('courseSelect');
    const datePicker = document.getElementById('startDate');
    const warningText = document.getElementById('dateWarningMessage');
    
    const selectedOption = courseDropdown.options[courseDropdown.selectedIndex];
    if (!selectedOption || courseDropdown.value === "") return;

    datePicker.disabled = false;
    datePicker.min = selectedOption.getAttribute('data-start');
    datePicker.max = selectedOption.getAttribute('data-end');
    datePicker.value = "";
    warningText.classList.add('hidden');
}

function enforceMeetingDaySelection(inputField) {
    const chosenDateValue = inputField.value;
    if (!chosenDateValue) return;

    const allowedDaysToken = document.getElementById('courseSelect').selectedOptions[0].getAttribute('data-days');
    const warningText = document.getElementById('dateWarningMessage');
    const submitBtn = document.getElementById('submitFormBtn');

    const weekdayNumericIndex = new Date(chosenDateValue + 'T00:00:00').getDay();
    const mappedLetterToken = ['U', 'M', 'T', 'W', 'R', 'F', 'S'][weekdayNumericIndex];

    if (allowedDaysToken.indexOf(mappedLetterToken) === -1) {
        inputField.value = ""; 
        inputField.style.border = "2px solid #bd2130"; 
        warningText.textContent = `❌ Reset: Course meets only on (${allowedDaysToken}). Invalid day cleared.`;
        warningText.classList.remove('hidden');
        submitBtn.disabled = true;
    } else {
        inputField.style.border = "1px solid #7a6855"; 
        warningText.classList.add('hidden');
        submitBtn.disabled = false;
    }
}

window.addEventListener('DOMContentLoaded', checkSecureSessionAuthentication);

function executeLogOut() {
    // FIXED: Directly drops the local session memory and routes back to the Flask exit gateway
    window.location.href = '/logout';       
}

function handleDateTypeToggle(userType, feedType) {
    processTabFiltering(userType, feedType);
}