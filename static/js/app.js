$(document).ready(function () {
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
                        <label><input type="checkbox" class="schoolCheckbox" value="${school.id}" data-title="${school.title}"> Select</label>
                    `;
                    schoolList.appendChild(schoolElement);
                });
            })
            .catch(error => console.error('Error fetching nearby schools:', error));
    }

    $('.apply-school-btn').on('click', function() {
        const childName = $(this).data('child-name');
        const childDob = $(this).data('child-dob');
        const childNhs = $(this).data('child-nhs');
        const childGender = $(this).data('child-gender');
        const childAge = $(this).data('child-age');
        const childId = $(this).data('child-id');
        const parentPostcode = $(this).data('parent-postcode');

        // Fill the child details in the form
        $('#childName').text(childName);
        $('#childDob').text(childDob);
        $('#childAge').text(childAge);
        $('#childNhs').text(childNhs);
        $('#childGender').text(childGender);
        $('#childId').val(childId);
        $('#parentPostcode').text(parentPostcode);

        // Fetch latitude and longitude using the parent's postcode
        fetch(`https://findthatpostcode.uk/postcodes/${parentPostcode}.json`)
            .then(response => response.json())
            .then(data => {
                const lat = data.data.attributes.location.lat;
                const lng = data.data.attributes.location.lon;

                // Prefill latitude and longitude fields
                $('#latitude').val(lat);
                $('#longitude').val(lng);

                // Also fill hidden fields
                $('#latHidden').val(lat);
                $('#lngHidden').val(lng);
            })
            .catch(error => {
                console.error('Error fetching location data:', error);
                alert('Unable to fetch location data. Please enter manually.');
            });

        // Reset the steps to start from step 1
        $('#step1').show();
        $('#step2').hide();
        $('#step3').hide();
        $('#step4').hide();
    });

    $('#searchSchools').on('click', function () {
        const latitude = $('#latitude').val();
        const longitude = $('#longitude').val();
        if (!latitude || !longitude) {
            alert('Please enter latitude and longitude.');
            return;
        }
        fetchNearbySchools(latitude, longitude);
        $('#latHidden').val(latitude);
        $('#lngHidden').val(longitude);
        $('#step1').hide();
        $('#step2').show();
    });

    $('#nextToStep3').on('click', function () {
        const selectedSchools = [];
        $('.schoolCheckbox:checked').each(function () {
            const schoolId = $(this).val();
            const schoolTitle = $(this).data('title');
            selectedSchools.push({
                id: schoolId,
                title: schoolTitle
            });
        });

        console.log('Selected Schools:', selectedSchools);

        if (selectedSchools.length === 0) {
            alert('Please select at least one school.');
            return;
        }

        $('#selectedSchools').empty();
        selectedSchools.forEach((school, index) => {
            $('#selectedSchools').append(`
                <div class="form-group">
                    <label for="preference${index}" class="school-title-label" data-school-title="${school.title}">Selected School ${index + 1}: ${school.title}</label>
                    <select class="form-control" id="preference${index}" name="preferences[]">
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                    </select>
                    <div class="form-check mt-2">
                        <input class="form-check-input sibling-checkbox" type="checkbox" value="${school.id}" id="siblingCheck${index}" data-index="${index}">
                        <label class="form-check-label" for="siblingCheck${index}">
                            Do you have any siblings in this school?
                        </label>
                    </div>
                    <div class="sibling-info mt-2" id="siblingInfo${index}" style="display:none;">
                        <div class="form-group">
                            <label for="siblingName${index}">Sibling Name</label>
                            <input type="text" class="form-control sibling-name" id="siblingName${index}" name="siblings[${index}][name]">
                        </div>
                        <div class="form-group">
                            <label for="siblingDob${index}">Sibling Date of Birth</label>
                            <input type="date" class="form-control sibling-dob" id="siblingDob${index}" name="siblings[${index}][dob]">
                        </div>
                        <div class="form-group">
                            <label for="siblingYearGroup${index}">Sibling Year Group</label>
                            <input type="text" class="form-control sibling-year-group" id="siblingYearGroup${index}" name="siblings[${index}][year_group]">
                        </div>
                    </div>
                </div>
            `);
        });

        $('.sibling-checkbox').on('change', function () {
            const index = $(this).data('index');
            if ($(this).is(':checked')) {
                $(`#siblingInfo${index}`).show();
            } else {
                $(`#siblingInfo${index}`).hide();
            }
        });

        $('#step2').hide();
        $('#step3').show();
    });

    $('#nextToStep4').on('click', function () {
        $('#confirmChildName').text($('#childName').text());
        $('#confirmChildDob').text($('#childDob').text());
        $('#confirmChildAge').text($('#childAge').text());
        $('#confirmChildNhs').text($('#childNhs').text());
        $('#confirmChildGender').text($('#childGender').text());

        $('#confirmationPreferences').empty();
        const siblingData = [];
        let hasPreferences = false;

        $('#selectedSchools .form-group').each(function (index) {
            const schoolTitle = $(this).find('.school-title-label').data('school-title');
            const preferenceValue = $(this).find('select').val();
            const siblingCheckbox = $(this).find('.sibling-checkbox').is(':checked');
            console.log(schoolTitle);

            if (schoolTitle && preferenceValue) {
                hasPreferences = true;
                const preference = {
                    preference: index + 1,
                    school_title: schoolTitle,
                    preference_value: preferenceValue,
                    siblings: []
                };

                let siblingDetails = '';
                if (siblingCheckbox) {
                    const siblingName = $(this).find('.sibling-name').val();
                    const siblingDob = $(this).find('.sibling-dob').val();
                    const siblingYearGroup = $(this).find('.sibling-year-group').val();

                    if (siblingName && siblingDob && siblingYearGroup) {
                        preference.siblings.push({
                            name: siblingName,
                            dob: siblingDob,
                            year_group: siblingYearGroup,
                            school_id: $(this).find('.sibling-checkbox').val()
                        });

                        siblingDetails = `
                            <p><strong>Sibling Name:</strong> ${siblingName}</p>
                            <p><strong>Sibling Date of Birth:</strong> ${siblingDob}</p>
                            <p><strong>Sibling Year Group:</strong> ${siblingYearGroup}</p>
                        `;
                    }
                }

                $('#confirmationPreferences').append(`
                    <div>
                        <p><strong>Selected School :</strong> ${schoolTitle}</p>
                        <p><strong>Preference Value:</strong> ${preferenceValue}</p>

                        ${siblingDetails}
                    </div>
                `);

                siblingData.push(preference);
            }
        });

        if (!hasPreferences) {
            alert('Please provide at least one preference.');
            return;
        }

        console.log('Sibling Data:', siblingData);

        $('<input>').attr({
            type: 'hidden',
            name: 'sibling_data',
            value: JSON.stringify(siblingData)
        }).appendTo('#applySchoolForm');

        $('#step3').hide();
        $('#step4').show();
    });

    $('#applySchoolForm').on('submit', function (e) {
        e.preventDefault();

        const selectedSchools = [];
        $('.schoolCheckbox:checked').each(function () {
            selectedSchools.push($(this).val());
        });
        $('#selectedSchoolIds').val(selectedSchools.join(','));

        console.log('Selected School IDs:', selectedSchools);

        $('#applySchoolForm')[0].submit();
    });

    $('#backToStep3').on('click', function () {
        $('#step4').hide();
        $('#step3').show();
    });

    $('#backToStep2').on('click', function () {
        $('#step3').hide();
        $('#step2').show();
    });

    $('#backToStep1').on('click', function () {
        $('#step2').hide();
        $('#step1').show();
    });

document.addEventListener("DOMContentLoaded", function() {
    var sidebar = document.querySelector('.sidebar');
    var toggleButton = document.querySelector('.menu-toggle');

    toggleButton.addEventListener('click', function() {
        sidebar.classList.toggle('active');
    });
});
});
 $(document).ready(function() {
    // View application details
    $('.view-application-btn').on('click', function() {
        var applicationId = $(this).data('application-id');
        $('#edit-application-form').hide();
        $('#applicationDetailsContent').show();
        $.ajax({
            url: '{% url "view_application_details" 0 %}'.replace('0', applicationId),
            method: 'GET',
            success: function(data) {
                var modalBody = $('#applicationDetailsModal .modal-body #applicationDetailsContent');
                modalBody.empty();
                modalBody.append('<p><strong>Application ID:</strong> ' + data.application_id + '</p>');
                modalBody.append('<p><strong>Child Name:</strong> ' + data.child_name + '</p>');
                modalBody.append('<p><strong>Child Date of Birth:</strong> ' + data.child_dob + '</p>');
                modalBody.append('<p><strong>Child Age:</strong> ' + data.child_age + '</p>');
                modalBody.append('<p><strong>Child NHS Number:</strong> ' + data.child_nhs_number + '</p>');
                modalBody.append('<p><strong>Child Gender:</strong> ' + data.child_gender + '</p>');
                modalBody.append('<p><strong>Parent Name:</strong> ' + data.parent_name + '</p>');
                modalBody.append('<p><strong>Parent Email:</strong> ' + data.parent_email + '</p>');
                modalBody.append('<p><strong>Parent Phone:</strong> ' + data.parent_phone + '</p>');
                modalBody.append('<p><strong>Applied On:</strong> ' + data.applied_on + '</p>');

                // Highlight status in green if offer_received
                if (data.status === 'offer_received') {
                    modalBody.append('<p><strong>Status:</strong> <span class="text-success">' + data.status + '</span></p>');
                } else {
                    modalBody.append('<p><strong>Status:</strong> ' + data.status + '</p>');
                }

                // Highlight offered school in green if not None
                if (data.offered_school_name) {
                    modalBody.append('<p><strong>Offered School:</strong> <span class="text-success">' + data.offered_school_name + '</span></p>');
                } else {
                    modalBody.append('<p><strong>Offered School:</strong> None</p>');
                }

                modalBody.append('<h5>Preferences</h5>');
                data.preferences.forEach(function(preference, index) {
                    modalBody.append('<p><strong>Selected School ' + (index + 1) + ':</strong></p>');
                    modalBody.append('<p><strong>School Name:</strong> ' + preference.school.name + '</p>');
                    modalBody.append('<p><strong>School Address:</strong> ' + preference.school.address + '</p>');
                    modalBody.append('<p><strong>School Phone:</strong> ' + preference.school.phone + '</p>');
                    modalBody.append('<p><strong>School Website:</strong> <a href="' + preference.school.website + '">' + preference.school.website + '</a></p>');
                    modalBody.append('<p><strong>School Email:</strong> ' + preference.school.email + '</p>');
                    modalBody.append('<p><strong>Preference:</strong> ' + preference.preference + '</p>');
                    if (preference.siblings.length > 0) {
                        modalBody.append('<h6>Siblings:</h6>');
                        preference.siblings.forEach(function(sibling) {
                            modalBody.append('<p>Name: ' + sibling.name + '</p>');
                            modalBody.append('<p>Date of Birth: ' + sibling.dob + '</p>');
                            modalBody.append('<p>Year Group: ' + sibling.year_group + '</p>');
                        });
                    }
                });
                $('#applicationDetailsModal').modal('show');
            },
            error: function(error) {
                console.error('Error fetching application details:', error);
            }
        });
    });
});