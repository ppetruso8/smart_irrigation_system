let now = new Date();
let curTime;
let hourlyItem;
let hourlyContainer = document.getElementById('hourly_container');
let wateringMode = document.querySelectorAll('select[name$="mode"]');

document.addEventListener("DOMContentLoaded", init, false);

function init() {
    /* Scroll to correct item in hourly forecast based on current time */
    // get current time and transform to format as in HTML
    now.setMinutes(0);  // round current time down to nearest hour 
    curTime = now.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
    }).replace(",", "");

    // find an item in HTML
    hourlyItem = Array.from(document.querySelectorAll('.hourly_item')).find(el => el.querySelector('.time')?.textContent.trim() === curTime);

    if (hourlyItem) {
        hourlyContainer.scrollTo({
            left: hourlyItem.offsetLeft - hourlyContainer.offsetLeft,
            behavior: "smooth"
        });
    } else {
        console.log("Error finding hourly item for current time:", curTime);
    }

    /* Custom watering amount field visibility */
    wateringMode.forEach(mode => {
        let sensorId = mode.closest("form").querySelector('input[name="sensor"]')?.value;
        if (sensorId) {
            toggleCustomAmount(mode, sensorId);
            mode.addEventListener("change", () => toggleCustomAmount(mode, sensorId));
        }
    });
}

// display custom amount form field if watering mode set to Custom
function toggleCustomAmount(selectElement, sensorId) {
    let customAmountField = document.getElementById(`custom_amount_${sensorId}`);
    if (selectElement.value === "Custom") {
        customAmountField.style.display = "block";
    } else {
        customAmountField.style.display = "none";
    }
}
