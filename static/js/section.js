$(document).ready(function () {
    $('#add-schedule-icon').click(function (event) {
        $('.schedule-add-error').hide();
        $('#classrooms').empty();
        $.ajax({
            url:"/lecture-schedule-add",
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.schedule-add-error').show();
                }
                else {

                    for (var i =0 ; i<data.classrooms.length;i++){
                        $("#classrooms")
                            .append("<option value='"+data.classrooms[i][0]+"'>"+data.classrooms[i][1]+"</option>")
                    }
                }
            });
        event.preventDefault()
    });
    $('#add-schedule').click(function () {
        $('.add-schedule-form').attr('action','/lecture-schedule-add').submit();
    });

    $(".schedule-details").click(function (event) {
        $('.schedule-details-error').hide();
        $("#classrooms-details").empty();
        $("#day").empty();
        $.ajax({
            url:"/lecture-schedule-details/"+$(this).data("id"),
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.schedule-details-error').show();
                }
                else {
                    console.log(data)
                    $("#start-time").attr('value',data.info[0][1]);
                    $("#end-time").attr('value',data.info[0][2]);

                    for (var i =0 ; i<data.classrooms.length;i++){
                        if (data.classrooms[i][1]===data.info[0][0]){

                            $("#classrooms-details")
                                .append("<option value='"+data.classrooms[i][0]+"' selected>"+data.classrooms[i][1]+"</option>")
                        }
                        else {
                            $("#classrooms-details")
                                .append("<option value='"+data.classrooms[i][0]+"'>"+data.classrooms[i][1]+"</option>")
                        }
                    }
                    for (var i =0 ; i<data.days.length;i++){
                        if (data.days[i]===data.info[0][3]){
                            $("#day")
                                .append("<option value='"+data.days[i]+"' selected>"+data.selected_day[data.days[i]]+"</option>")
                        }
                        else {
                            $("#day")
                                .append("<option value='"+data.days[i]+"'>"+data.selected_day[data.days[i]]+"</option>")
                        }
                    }

                }
            });
        event.preventDefault()
    });
    $('#edit-schedule').click(function () {
        $('.edit-schedule-form').attr('action','/lecture-schedule-edit').submit()
    });
    $('#delete-schedule').click(function () {
        $('.edit-schedule-form').attr('action','/lecture-schedule-delete').submit()
    });

    $("#add-record-icon").click(function (event) {
        $('.lecture-add-error').hide();
        $("#classrooms-add-lecture").empty();
        $.ajax({
            url:"/lecture-add",
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.lecture-add-error').show();

                }
                else {
                    for (var i =0 ; i<data.classrooms.length;i++){
                        $("#classrooms-add-lecture")
                            .append("<option value='"+data.classrooms[i][0]+"'>"+data.classrooms[i][1]+"</option>")
                    }

                }
            });
        event.preventDefault()
    });
    $('#add-lecture-btn').click(function () {
        $('.add-lecture-form').attr('action','/lecture-add').submit();
    });

    $(".lecture-details").click(function (event) {
        $('.lecture-details-error').hide();
        $("#lecture-classroom").empty();
        $('#table-lecture-edit-body').empty();
        $.ajax({
            url:"/lecture-details/"+$(this).data('id'),
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.lecture-details-error').show();
                    console.log(data.error)
                }
                else {
                    $('#lecture-start').attr('value',data.lecture[0][2]);
                    $('#lecture-end').attr('value',data.lecture[0][3]);
                    $('#lecture-day').attr('value',data.lecture[0][4]);
                    $('#lecture-classroom-instructor').attr('value',data.classroom_ins);
                    for (var i =0 ; i<data.classrooms.length;i++){

                        if (data.classrooms[i][0]===data.lecture[0][1]){

                            console.log(data.classrooms[i][1])
                            $("#lecture-classroom")
                                .append("<option value='"+data.classrooms[i][0]+"' selected>"+data.classrooms[i][1]+"</option>")
                        }
                        else {
                            $("#lecture-classroom")
                                .append("<option value='"+data.classrooms[i][0]+"'>"+data.classrooms[i][1]+"</option>")
                        }

                    }
                    for (var i=0; i< data.students_attend.length;i++){
                        $('#table-lecture-edit-body').append("<tr><td>"+data.students_attend[i][1]+
                            "</td><td>"+data.students_attend[i][2]+" "+data.students_attend[i][3]+"</td>" +
                            "<td><input type='checkbox' class='form-control' name='student-attend' value='"
                            +data.students_attend[i][0]+"' style='width:20px;margin-right:25px;' checked>" +
                            "</td></tr>")
                    }

                    for (var i=0; i< data.students.length;i++){
                        $('#table-lecture-edit-body').append("<tr><td>"+data.students[i][1]+
                            "</td><td>"+data.students[i][2]+" "+data.students[i][3]+"</td>" +
                            "<td><input type='checkbox' class='form-control' name='student-attend' value='"
                            +data.students[i][0]+"' style='width:20px;margin-right:25px;'>" +
                            "</td></tr>")
                    }
                    console.log(data)
                }
            });
        event.preventDefault()
    });

    $('#delete-lecture-btn').click(function () {
        $('.edit-lecture-form').attr('action','/lecture-delete').submit();
    });
    $('#edit-lecture-btn').click(function () {
        $('.edit-lecture-form').attr('action','/lecture-edit').submit();
    });

    $("#add-student-record-icon").click(function (event) {
        $('.student-add-error').hide();
        $("#students-list").empty();
        $('.table-student-add-body').empty();
        $.ajax({
            url:"/student-add",
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.student-add-error').show();
                    console.log(data.error)
                }
                else {

                    for(var i= 0; i< data.users.length;i++){
                        $("#students-list")
                            .append("<option value='"+data.users[i][0]+"'>"+data.users[i][1]+" - "+data.users[i][2]+" "+data.users[i][3] +"</option>")
                    }

                    for (var i=0; i< data.lectures.length;i++){
                        $('.table-student-add-body').append("<tr><td>"+data.lectures[i][1]+
                            "</td><td>"+data.lectures[i][2]+" - "+data.lectures[i][3]+"</td>" +
                            "<td><input type='checkbox' class='form-control' name='lecture-attend' value='"
                            +data.lectures[i][0]+"' style='width:20px;margin-right:25px;'>" +
                            "</td></tr>")
                    }
                    console.log(data)
                }
            });
        event.preventDefault()
    });

    $('#add-student-lecture').click(function () {
        $('.add-student-form').attr('action','/student-add').submit();
    });

    $(".student-details").click(function (event) {
        $('.student-details-error').hide();
        $('#table-lecture-details-body').empty();
        $.ajax({
            url:"/student-details/"+$(this).data('id'),
            type:'GET',
        })
            .done(function (data) {
                if (data.error){
                    $('.student-add-error').show();
                }
                else {
                    $('#student-details').attr('value',data.user[0][1]+" - "+data.user[0][2]+" "+data.user[0][3]);
                    $('#student-value').attr('value',data.user[0][0]);

                    for (var i=0; i< data.lectures_attend.length;i++){
                        $('#table-lecture-details-body').append("<tr><td>"+data.lectures_attend[i][1]+
                            "</td><td>"+data.lectures_attend[i][2]+" - "+data.lectures_attend[i][3]+"</td>" +
                            "<td><input type='checkbox' class='form-control' name='lecture-attend' value='"
                            +data.lectures_attend[i][0]+"' style='width:20px;margin-right:25px;' checked>" +
                            "</td>" +
                            "<td>"+data.student_pre[i]+"</td>"+
                            "</tr>")
                    }


                    for (var i=0; i< data.lectures.length;i++){
                        $('#table-lecture-details-body').append("<tr><td>"+data.lectures[i][1]+
                            "</td><td>"+data.lectures[i][2]+" - "+data.lectures[i][3]+"</td>" +
                            "<td><input type='checkbox' class='form-control' name='lecture-attend' value='"
                            +data.lectures[i][0]+"' style='width:20px;margin-right:25px;'>" +
                            "</td>" +
                            "<td>"+"0.00 %"+"</td>"+
                            "</tr>")
                    }
                    console.log(data)
                }
            });
        event.preventDefault()
    });
    $('#edit-student-btn').click(function () {
        $('.edit-student-form').attr('action','/student-edit').submit();
    });
    $('#delete-student-btn').click(function () {
        $('.edit-student-form').attr('action','/student-delete').submit();
    });





});