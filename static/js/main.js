$(document).ready(function () {
        var hello="hello";
    //create multiple tables
    var id=['#table-classes', '#table-lecture-dates','#table-lectures',
        '#table-users',
        '#table-courses','#table-students','#table-presents','#instructor-courses',
        '#instructor-lecture-dates','#instructor-students','#instructor-lectures',
        '#student-courses','#student-lecture-dates','#student-lectures','#admin-institutes'];

    var size=[200,180,180,480,200,180,320,300,180,180,180,300,180,180,300];

    var name=['الفصول','جدول المحاضرات','المحاضرات',"المستخدمين",
        'الشعب','الطلاب','الطلاب','الشعب','جدول المحاضرات','الطلاب','المحاضرات','الشعب','جدول المحاضرات','المحاضرات','المؤسسات'];

    var responsive=[[1,3,2,4],[1,3,2],[1,3,2],
        [0,5,6,4,3,2],[0,4,5,6,3,2],[1,3,4,2],[1,2],[0,1,5,4,3],[1,3,2],[1,3,4,2],[1,3,2],[0,1,4,5,3],[1,3,2],[1,3,2],[0,1,5,4,3]];

    var resp_result=[responsive.length];

    for(var i=0;i<id.length;i++){
        for(var j =0 ;j<responsive[i].length;j++){
                resp_result[j]={ responsivePriority: responsive[i][j] };
        }
        $(id[i]).dataTable({
                paging: false,
                scrollY: size[i],
                "order": [],
                ordering:true,
                responsive: true,
                columns:resp_result ,
                "language":
                    {
                        "sProcessing": "جارٍ التحميل...",
                        "sLengthMenu": "أظهر _MENU_ مدخلات",
                        "sZeroRecords": "لم يتم العثور على أي سجلات",
                        "sInfo": name[i]+" &nbsp; &nbsp; _TOTAL_",
                        "sInfoEmpty": name[i]+" &nbsp; &nbsp; _TOTAL_",
                        "sInfoFiltered": "",
                        "sInfoPostFix": "",
                        "sSearch": "",
                        "sUrl": "",
                        "oPaginate": {
                            "sFirst": "الأول",
                            "sPrevious": "السابق",
                            "sNext": "التالي",
                            "sLast": "الأخير"
                        }
                    }
            }

        );
        resp_result=[];

    }

    //configure some tables
    var id1=['#table-classes', '#table-lecture-dates','#table-lectures','#table-students'];
    var idTable=["#add-class-model","#add-lecture-date","#add-lecture","#add-student-model"];
    var ids=["add-class-icon","add-schedule-icon","add-record-icon","add-student-record-icon"];
    for(var i=0;i<id1.length;i++){
        $(id1[i]+'_wrapper').children().first().children().first().append($(id1[i]+'_info'));
        $(id1[i]+'_wrapper').children().first().after("<hr>");
        $(id1[i]+'_filter').children().first().children().first().attr('placeholder','ابحث...');
        $(id1[i]+'_filter').children().first().before(
            '<a  href="#"  id='+ids[i]+' data-toggle="modal" data-target='+idTable[i]+'>' +
            '<img src="/static/resources/images/add-icon-big.svg" width="26px" height="26px"></a>')

    }

    var id2=['#table-presents'];
    for(var i=0;i<id2.length;i++){
        $(id2[i]+'_wrapper').children().first().children().first().append($(id2[i]+'_info'));
        $(id2[i]+'_wrapper').children().first().children().last().html(
            '<div class="pres-table" style="padding-top: 10px;color: var(--theme-primary);">%73</div>');
        $(id2[i]+'_wrapper').children().first().after("<hr>");
    }

    var id3=['#table-users','#instructor-courses','#table-courses','#instructor-lecture-dates',
        '#instructor-students','#instructor-lectures','#student-courses','#student-lecture-dates',
        '#student-lectures','#admin-institutes'];

    for(var i=0;i<id3.length;i++){
        $(id3[i]+'_wrapper').children().first().children().first().append($(id3[i]+'_info'));
        $(id3[i]+'_wrapper').children().first().after("<hr>");
        $(id3[i]+'_filter').children().first().children().first().attr('placeholder','ابحث...');
    }

    $('#table-courses_filter').children().first().before(
        '<a href="#" data-toggle="modal" data-target="#section-add" id="section-add-btn" >' +
        '<img src="static/resources/images/add-icon-big.svg" width="26px" height="26px"></a>');

    //create progress circle
    $('.progress-circle').circleProgress({
        startAngle:0,
        thickness:10,
        animation:false,
        emptyFill:"#c1272d",
        // value: 0.64,
        size: 80,
        fill: {
            color:"#549a52"
        }
    });

});