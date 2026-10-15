'use strict';
const allDay=document.getElementById('all-day');
const times=document.getElementById('time-fields');
function toggleTimes(){times.hidden=allDay.checked;times.querySelectorAll('input').forEach(x=>x.required=!allDay.checked);}
allDay.addEventListener('change',toggleTimes);toggleTimes();
const startDate=document.getElementById('start-date'),endDate=document.getElementById('end-date');
startDate.addEventListener('change',()=>{if(!endDate.value)endDate.value=startDate.value;});
const eventForm=document.getElementById('event-form');
eventForm.addEventListener('input',()=>{const download=document.querySelector('#ics-form button');if(download){download.disabled=true;document.getElementById('unsaved-note').hidden=false;}});
