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

function resetTabFilters(userType, feedType) {
    let prefix = 'st';
    if (userType === 'faculty') prefix = 'fa';
    if (userType === 'proctorOpen') prefix = 'prOpen';
    if (userType === 'proctorAgreed') prefix = 'prAgreed';

    // Clear dates and dropdowns
    const startInput = document.getElementById(`${prefix}Start`);
    if (startInput) startInput.value = '';
    
    const endInput = document.getElementById(`${prefix}End`);
    if (endInput) endInput.value = '';
    
    const sortInput = document.getElementById(`${prefix}Sort`);
    if (sortInput) sortInput.value = 'desc';

    // Reset radio buttons to 'submission'
    const defaultRadio = document.querySelector(`input[name="${prefix}DateType"][value="submission"]`);
    if (defaultRadio) defaultRadio.checked = true;

    // Reset faculty course dropdown if it exists
    const courseSelect = document.getElementById('faCourse');
    if (courseSelect && userType === 'faculty') courseSelect.value = 'ALL';

    // Run the filter engine to restore all items instantly
    processTabFiltering(userType, feedType);
}

function processTabFiltering(userType, feedType) {
    const container = document.getElementById(feedType);
    if (!container) return;

    // Grab all target child cards within this specific feed container
    const items = Array.from(container.querySelectorAll('.exam-card'));
    if (items.length === 0) return;

    // 1. Map the parameter scope context prefixes cleanly
    let prefix = 'st';
    if (userType === 'faculty') prefix = 'fa';
    if (userType === 'proctorOpen') prefix = 'prOpen';
    if (userType === 'proctorAgreed') prefix = 'prAgreed';

    // 2. Safely extract interactive input field values
    const dateTypeInput = document.querySelector(`input[name="${prefix}DateType"]:checked`);
    const dateType = dateTypeInput ? dateTypeInput.value : 'submission';
    
    const startDateElement = document.getElementById(`${prefix}Start`);
    const endDateElement = document.getElementById(`${prefix}End`);
    const sortElement = document.getElementById(`${prefix}Sort`);

    const startDateVal = startDateElement ? startDateElement.value : '';
    const endDateVal = endDateElement ? endDateElement.value : '';
    const sortOrder = sortElement ? sortElement.value : 'desc';

    // Faculty drop-down filter parsing metric
    const courseSelect = document.getElementById('faCourse');
    const selectedCourse = courseSelect ? courseSelect.value : 'ALL';

    // 3. Convert input strings to numeric timestamps (null if left blank)
    const filterStart = startDateVal ? new Date(startDateVal + "T00:00:00").getTime() : null;
    const filterEnd = endDateVal ? new Date(endDateVal + "T23:59:59").getTime() : null;

    // 4. Map and evaluate each item's visibility status
    const itemsWithDates = items.map(item => {
        const rawSubDate = item.getAttribute('data-submission-date');
        const rawExamDate = item.getAttribute('data-exam-date');
        const itemCourse = item.getAttribute('data-course'); // Used by Faculty tab

        const subTime = rawSubDate ? new Date(rawSubDate + "T00:00:00").getTime() : 0;
        const examTime = rawExamDate ? new Date(rawExamDate + "T00:00:00").getTime() : 0;
        
        // Pick which date timeline to use based on the radio button choice
        const activeTime = (dateType === 'submission') ? subTime : examTime;

        let isVisible = true;

        // FIXED: Boundary conditions only trip if the user filled out that specific date input
        if (filterStart && activeTime < filterStart) isVisible = false;
        if (filterEnd && activeTime > filterEnd) isVisible = false;

        // Faculty Course tracking evaluation check
        if (selectedCourse !== 'ALL' && itemCourse && itemCourse !== selectedCourse) {
            isVisible = false;
        }

        // Toggle card layout visibility without wiping out DOM element records
        item.style.display = isVisible ? '' : 'none';
        
        return { element: item, time: activeTime };
    });

    // 5. Run the mathematical layout sorting logic
    itemsWithDates.sort((a, b) => {
        return (sortOrder === 'desc') ? b.time - a.time : a.time - b.time;
    });

    // 6. Re-append nodes back into the DOM to instantly update screen sequence order
    itemsWithDates.forEach(itemObj => {
        container.appendChild(itemObj.element);
    });
}
