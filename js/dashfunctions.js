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

function handleColumnDateTypeToggle(filterKey, feedType) {
    processColumnFiltering(filterKey, feedType);
}

function processTabFiltering(userType, feedType) {
    applyFeedFiltering(feedType);
}

function processColumnFiltering(filterKey, feedType) {
    applyFeedFiltering(feedType);
}

function clearFilters(feedType) {
    const filterConfig = {
        examFeed: { dateTypeName: 'stDateType', startId: 'stStart', endId: 'stEnd', sortId: 'stSort' },
        facultyRequestsFeed: { dateTypeName: 'faDateType', startId: 'faStart', endId: 'faEnd', sortId: 'faSort', courseId: 'faCourse' },
        openProctorFeed: { dateTypeName: 'openDateType', startId: 'openStart', endId: 'openEnd', sortId: 'openSort' },
        agreedProctorFeed: { dateTypeName: 'agreedDateType', startId: 'agreedStart', endId: 'agreedEnd', sortId: 'agreedSort' }
    };

    const config = filterConfig[feedType];
    if (!config) return;

    const dateRadios = document.querySelectorAll(`input[name="${config.dateTypeName}"]`);
    dateRadios.forEach(radio => {
        if (radio.value === 'submission') radio.checked = true;
    });

    document.getElementById(config.startId)?.value && (document.getElementById(config.startId).value = '');
    document.getElementById(config.endId)?.value && (document.getElementById(config.endId).value = '');
    const sortElement = document.getElementById(config.sortId);
    if (sortElement) sortElement.value = 'desc';
    if (config.courseId) document.getElementById(config.courseId)?.value = 'ALL';

    applyFeedFiltering(feedType);
}

function applyFeedFiltering(feedType) {
    const filterConfig = {
        examFeed: { dateTypeName: 'stDateType', startId: 'stStart', endId: 'stEnd', sortId: 'stSort' },
        facultyRequestsFeed: { dateTypeName: 'faDateType', startId: 'faStart', endId: 'faEnd', sortId: 'faSort', courseId: 'faCourse' },
        openProctorFeed: { dateTypeName: 'openDateType', startId: 'openStart', endId: 'openEnd', sortId: 'openSort' },
        agreedProctorFeed: { dateTypeName: 'agreedDateType', startId: 'agreedStart', endId: 'agreedEnd', sortId: 'agreedSort' }
    };

    const config = filterConfig[feedType];
    if (!config) return;

    const feedContainer = document.getElementById(feedType);
    if (!feedContainer) return;

    const selectedDateType = document.querySelector(`input[name="${config.dateTypeName}"]:checked`)?.value || 'submission';
    const dateAttribute = selectedDateType === 'exam' ? 'data-exam-date' : 'data-submission-date';
    const startValue = document.getElementById(config.startId)?.value;
    const endValue = document.getElementById(config.endId)?.value;
    const sortDirection = document.getElementById(config.sortId)?.value || 'desc';
    const selectedCourse = config.courseId ? document.getElementById(config.courseId)?.value : 'ALL';

    const fromTime = startValue ? new Date(`${startValue}T00:00:00`).getTime() : null;
    const toTime = endValue ? new Date(`${endValue}T23:59:59`).getTime() : null;

    const cards = Array.from(feedContainer.querySelectorAll('.exam-card'));
    const visibleCards = cards.filter(card => {
        if (selectedCourse && selectedCourse !== 'ALL' && config.courseId) {
            const courseTag = card.dataset.course;
            if (!courseTag || courseTag !== selectedCourse) {
                return false;
            }
        }

        const rawDate = card.getAttribute(dateAttribute);
        if (!rawDate) {
            return true;
        }

        const cardTime = new Date(`${rawDate}T00:00:00`).getTime();
        if (fromTime !== null && cardTime < fromTime) return false;
        if (toTime !== null && cardTime > toTime) return false;
        return true;
    });

    cards.forEach(card => card.classList.toggle('hidden', !visibleCards.includes(card)));

    visibleCards.sort((a, b) => {
        const aValue = new Date(`${a.getAttribute(dateAttribute)}T00:00:00`).getTime() || 0;
        const bValue = new Date(`${b.getAttribute(dateAttribute)}T00:00:00`).getTime() || 0;
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
    });

    visibleCards.forEach(card => feedContainer.appendChild(card));
}
