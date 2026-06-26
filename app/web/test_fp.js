const { JSDOM } = require('jsdom');
const dom = new JSDOM(`<input id="filterStart" />`);
global.window = dom.window;
global.document = dom.window.document;
global.Node = dom.window.Node;
global.HTMLElement = dom.window.HTMLElement;
global.navigator = { userAgent: 'node' };
const flatpickr = require('flatpickr');

const fpConfig = {
      enableTime: true,
      enableSeconds: false,
      dateFormat: "F j, Y g:i K", // "September 9, 2015 9:00 PM"
      minDate: new Date(),
      maxDate: new Date(),
      time_24hr: false,
      monthSelectorType: "static", // Matches Image 1 header
      locale: {
        firstDayOfWeek: 1, // Start on Monday
        weekdays: {
          shorthand: ['S', 'M', 'T', 'W', 'T', 'F', 'S'] // Matches Image 1 single letter days
        }
      },
      onReady: function (selectedDates, dateStr, instance) {
        try {
            const calendarContainer = instance.calendarContainer;
            calendarContainer.classList.add('tejas-custom-layout');

            // Create main wrapper for left panel (calendar) and right panel (time)
            const mainFlex = document.createElement('div');
            mainFlex.className = 'tejas-main-flex';

            const leftPanel = document.createElement('div');
            leftPanel.className = 'tejas-left-panel';

            // Move native month header and calendar grid into left panel
            if (instance.monthNav) {
            leftPanel.appendChild(instance.monthNav);
            }
            const innerContainer = calendarContainer.querySelector('.flatpickr-innerContainer');
            if (innerContainer) {
            leftPanel.appendChild(innerContainer);
            }

            // Time list container
            const timeListContainer = document.createElement('div');
            timeListContainer.className = 'tejas-time-list';

            // Generate Hours
            const times = [];
            for (let i = 0; i < 24; i++) {
            const ampm = i >= 12 ? 'PM' : 'AM';
            const hour12 = i % 12 === 0 ? 12 : i % 12;
            times.push({ val: i, label: `${hour12}:00 ${ampm}` });
            }

            times.forEach(t => {
            const btn = document.createElement('div');
            btn.className = 'tejas-time-item';
            btn.textContent = t.label;
            btn.dataset.hour = t.val;
            btn.addEventListener('click', () => {
                if (!instance.selectedDates.length) return;
                const d = new Date(instance.selectedDates[0]);
                d.setHours(t.val, 0, 0, 0);
                instance.setDate(d, true);
            });
            timeListContainer.appendChild(btn);
            });

            // Assemble main flex container
            mainFlex.appendChild(leftPanel);
            mainFlex.appendChild(timeListContainer);

            // Insert at top of calendar
            calendarContainer.insertBefore(mainFlex, calendarContainer.firstChild);

            // Footer
            const footer = document.createElement('div');
            footer.className = 'tejas-picker-footer';
            
            const todayBtn = document.createElement('div');
            todayBtn.className = 'tejas-today-btn';
            todayBtn.textContent = 'TODAY';
            todayBtn.addEventListener('click', () => {
            instance.setDate(new Date(), true);
            });
            
            const selectedText = document.createElement('div');
            selectedText.className = 'tejas-selected-text';
            
            footer.appendChild(todayBtn);
            footer.appendChild(selectedText);
            calendarContainer.appendChild(footer);

            // Update UI Function
            const updateUI = () => {
            if (!instance.selectedDates.length) return;
            const d = instance.selectedDates[0];
            
            // Update footer text
            const months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
            const month = months[d.getMonth()];
            const day = d.getDate();
            const year = d.getFullYear();
            const h = d.getHours();
            const ampm = h >= 12 ? 'PM' : 'AM';
            const h12 = h % 12 === 0 ? 12 : h % 12;
            selectedText.textContent = `${month} ${day}, ${year} ${h12}:00 ${ampm}`;

            // Highlight active hour
            timeListContainer.querySelectorAll('.tejas-time-item').forEach(el => {
                if (parseInt(el.dataset.hour, 10) === h) {
                el.classList.add('active');
                } else {
                el.classList.remove('active');
                }
            });
            };

            instance.updateUI = updateUI;
            updateUI();
        } catch(err) {
            console.error("ONREADY ERR:", err);
        }
      },
      onValueUpdate: function (selectedDates, dateStr, instance) {
        if (instance.updateUI) instance.updateUI();
      }
};

try {
  const fp = flatpickr(document.getElementById('filterStart'), { ...fpConfig, defaultDate: new Date() });
  console.log("SUCCESS!", fp.input.value);
} catch (e) {
  console.error("FAIL", e);
}
