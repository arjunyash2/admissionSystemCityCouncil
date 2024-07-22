function fetchNearbySchools(lat, lng) {
  const apiKey = 'iW9ceziSt7BhDuG3FZGbuRkk09ETfoDJznAqwbcjMBw';
  const url = `https://discover.search.hereapi.com/v1/discover?at=${lat},${lng}&q=schools&apiKey=${apiKey}`;

  fetch(url)
    .then(response => response.json())
    .then(data => {
      const schoolList = document.getElementById('schoolList');
      schoolList.innerHTML = '';
      data.items.forEach(school => {
        const schoolElement = document.createElement('div');
        schoolElement.innerHTML = `
          <p><strong>${school.title}</strong></p>
          <p>Distance: ${school.distance} meters</p>
          <label><input type="checkbox" class="schoolCheckbox" value="${school.id}"> Select</label>
        `;
        schoolList.appendChild(schoolElement);
      });
    })
    .catch(error => console.error('Error fetching nearby schools:', error));
}

$('#deleteChildModal').on('show.bs.modal', function (event) {
  var button = $(event.relatedTarget);
  var childId = button.data('child-id');
  var childName = button.data('child-name');

  var modal = $(this);
  modal.find('.modal-body #childNameToDelete').text(childName);
  modal.find('.modal-footer #deleteChildForm').attr('action', '{% url "delete_child" 0 %}'.replace('0', childId));
});

$('#applySchoolModal').on('show.bs.modal', function (event) {
  var button = $(event.relatedTarget);
  var childId = button.data('child-id');
  var childName = button.data('child-name');
  var childDob = button.data('child-dob');
  var childNhs = button.data('child-nhs');
  var childGender = button.data('child-gender');
  var childAge = button.data('child-age');

  var modal = $(this);
  modal.find('#childName').text(childName);
  modal.find('#childDob').text(childDob);
  modal.find('#childNhs').text(childNhs);
  modal.find('#childGender').text(childGender);
  modal.find('#childAge').text(childAge);
  modal.find('#childId').val(childId);  // Set the hidden field value
});

$('#searchSchools').on('click', function() {
  var latitude = $('#latitude').val();
  var longitude = $('#longitude').val();
  if (!latitude || !longitude) {
    alert('Please enter latitude and longitude.');
    return;
  }
  fetchNearbySchools(latitude, longitude);
  $('#latHidden').val(latitude);
  $('#lngHidden').val(longitude);
});

$('#applySchoolForm').on('submit', function() {
  var selectedSchools = [];
  $('.schoolCheckbox:checked').each(function() {
    selectedSchools.push($(this).val());
  });
  $('#selectedSchoolIds').val(selectedSchools.join(','));
});
