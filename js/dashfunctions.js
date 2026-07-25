/*
*   This file contains all Javascript functions for the dashboard, handling tab visibility, data valitation, filtering, and more.
*   This file is required for a lot of the "flashy" functionality included in this form, so theoretically much of this is not strictly necessary
*   for the minimum desired functionality. It does, however, do a lot to improve the user experience.
*
*   Functions are organized in no particular order.
*/

// Important for tab-control and visibility based on role.
let tabVisibilityCriteria = { 'tab1': false, 'tab2': false, 'tab3': false };

/* 
    Checks the user's role and sets the visibility of each tab accordingly.
*/
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

/* 
    Enables/disables the tabs based on the user's role and sets up tab-switching functionality.
*/
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

window.addEventListener('DOMContentLoaded', checkSecureSessionAuthentication);


/* 
    "Activates" a tab and updates its accessibility attributes.
*/
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

/*
    Logout redirect.
*/
function executeLogOut() {
    window.location.href = '/logout';       
}

/* 
    Handles the toggle for date-type (submission date vs request date) filtering.
*/
function handleDateTypeToggle(userType, feedType) {
    processTabFiltering(userType, feedType);
}

/* 
    Resets all filters in the tab and re-displays all items (the default).
*/
function resetTabFilters(userType, feedType) {
    let prefix = 'st';
    if (userType === 'faculty') prefix = 'fa';
    if (userType === 'proctorOpen') prefix = 'prOpen';
    if (userType === 'proctorAgreed') prefix = 'prAgreed';

    const startInput = document.getElementById(`${prefix}Start`);
    if (startInput) startInput.value = '';
    
    const endInput = document.getElementById(`${prefix}End`);
    if (endInput) endInput.value = '';
    
    const sortInput = document.getElementById(`${prefix}Sort`);
    if (sortInput) sortInput.value = 'desc';

    const defaultRadio = document.querySelector(`input[name="${prefix}DateType"][value="submission"]`);
    if (defaultRadio) defaultRadio.checked = true;

    const courseSelect = document.getElementById('faCourse');
    if (courseSelect && userType === 'faculty') courseSelect.value = 'ALL';

    processTabFiltering(userType, feedType);
}

/* 
    Processes the filtering and sorting based on user input.
*/
function processTabFiltering(userType, feedType) {
    const container = document.getElementById(feedType);
    if (!container) return;

    const items = Array.from(container.querySelectorAll('.exam-card'));
    if (items.length === 0) return;

    let prefix = 'st';
    if (userType === 'faculty') prefix = 'fa';
    if (userType === 'proctorOpen') prefix = 'prOpen';
    if (userType === 'proctorAgreed') prefix = 'prAgreed';

    const dateTypeInput = document.querySelector(`input[name="${prefix}DateType"]:checked`);
    const dateType = dateTypeInput ? dateTypeInput.value : 'submission';
    
    const startDateElement = document.getElementById(`${prefix}Start`);
    const endDateElement = document.getElementById(`${prefix}End`);
    const sortElement = document.getElementById(`${prefix}Sort`);

    const startDateVal = startDateElement ? startDateElement.value : '';
    const endDateVal = endDateElement ? endDateElement.value : '';
    const sortOrder = sortElement ? sortElement.value : 'desc';

    const courseSelect = document.getElementById('faCourse');
    const selectedCourse = courseSelect ? courseSelect.value : 'ALL';

    const filterStart = startDateVal ? new Date(startDateVal + "T00:00:00").getTime() : null;
    const filterEnd = endDateVal ? new Date(endDateVal + "T23:59:59").getTime() : null;

    const itemsWithDates = items.map(item => {
        const rawSubDate = item.getAttribute('data-submission-date');
        const rawExamDate = item.getAttribute('data-exam-date');
        const itemCourse = item.getAttribute('data-course'); // Used by Faculty tab

        const subTime = rawSubDate ? new Date(rawSubDate + "T00:00:00").getTime() : 0;
        const examTime = rawExamDate ? new Date(rawExamDate + "T00:00:00").getTime() : 0;
        
        const activeTime = (dateType === 'submission') ? subTime : examTime;

        let isVisible = true;

        // Makes it so that you don't need a date range to filter.
        if (filterStart && activeTime < filterStart) isVisible = false;
        if (filterEnd && activeTime > filterEnd) isVisible = false;

        if (selectedCourse !== 'ALL' && itemCourse && itemCourse !== selectedCourse) {
            isVisible = false;
        }

        item.style.display = isVisible ? '' : 'none';
        
        return { element: item, time: activeTime };
    });

    itemsWithDates.sort((a, b) => {
        return (sortOrder === 'desc') ? b.time - a.time : a.time - b.time;
    });

    itemsWithDates.forEach(itemObj => {
        container.appendChild(itemObj.element);
    });
}