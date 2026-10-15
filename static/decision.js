'use strict';
const statusField = document.getElementById('decision-status');
const normalFields = document.getElementById('normal-fields');
const skipFields = document.getElementById('skip-fields');
const reason = document.getElementById('skip-reason');
const topicField = document.getElementById('topic');
const subField = document.getElementById('topic-sub');
const newTopic = document.querySelector('[name=new_topic]');
const subOptions = Array.from(subField.options).map(o => o.cloneNode(true));
function updateSubs() {
  const previous = subField.value;
  subField.replaceChildren(...subOptions.filter(o => !o.value || o.dataset.parent === topicField.value).map(o => o.cloneNode(true)));
  subField.value = Array.from(subField.options).some(o => o.value === previous) ? previous : '';
}
function updateStatus() {
  const skip = statusField.value === 'ignored';
  normalFields.hidden = skip;
  normalFields.querySelectorAll('input,select,textarea').forEach(e => e.disabled = skip);
  skipFields.hidden = !skip;
  reason.required = skip;
  reason.disabled = !skip;
  updateNewTopic();
}
function updateNewTopic() {
  const disabled = statusField.value === 'ignored' || Boolean(newTopic.value.trim());
  topicField.disabled = disabled;
  subField.disabled = disabled;
}
statusField.addEventListener('change', updateStatus);
topicField.addEventListener('change', updateSubs);
newTopic.addEventListener('input', updateNewTopic);
updateSubs();
updateStatus();
