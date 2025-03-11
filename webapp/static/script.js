let now = new Date();
let curTime;
let hourlyItem;
let hourlyContainer = document.getElementById('hourly_container');

document.addEventListener("DOMContentLoaded", init, false);
document.getElementById("clickMe").onclick = doFunction;

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
        console.log("Error finding hourly item for current time:", currentTime);
    }
}
