const express = require('express');
let bodyParser = require('body-parser');
const process = require('process');
const app = express();
const port = 3131;

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({extended: true}));




const jscodetoeval = `
class Rdrf {
    log(msg) {
        console.log(msg);
    }

    get(...anything) {
        console.log("A function is calling RDRF.get ADSAFE - ignoring...");
    }
}


RDRF = new Rdrf();

patient = {"sex": "1", "date_of_birth": "2000-05-10"};

context = {
    'FHconsentDate': '09-05-2019',
    'DateOfAssessment': '10-05-2019',
    'fhAgeAtConsent': '18',
    'fhAgeAtAssessment': '18',
    'CDEIndexOrRelative': 'fh_is_index',
    'CDEfhDutchLipidClinicNetwork': '24',
    'CDE00024': 'Definite',
    'CDE00013': 10.0,
    'CDE00019': 10.0,
    'PlasmaLipidTreatment': 'FAEzetimibe/atorvastatin20',
    'LDLCholesterolAdjTreatment': '21.74',
    'CDE00005': '',
    'FHPackYears': '',
    'FHAlcohol': '',
    'FHHypertriglycerd': '',
    'CDE00006': '',
    'CDE00008': '',
    'CDE00009': '',
    'FHHeartRate': '',
    'CDE00007': '',
    'CDE00010': '',
    'HbA1c': '',
    'ChronicKidneyDisease': '',
    'FHeGFR': '',
    'FHHypothyroidism': '',
    'FHTSH': '',
    'FHHepaticSteatosis': '',
    'FHObesity': '',
    'CDEHeight': 1.82,
    'CDEWeight': 86.0,
    'CDEBMI': '25.96',
    'CDEBMIPercentile': '',
    'FHWaistCirc': '',
    'FHCVDOther': ''
}

function bad(value) {
    return  (value == null) || ( value == undefined) || isNaN(value);
}


function convertDate(datestring) {
     // use this to on patient demographics dates
    var dateParts = datestring.split("-");
    var day = parseInt(dateParts[2]);
    var month = parseInt(dateParts[1]);
    var year = parseInt(dateParts[0]);
    return new Date(year,month,day);
}

function convertDate2(datestring) {
    // date values in clinical form parsed this way
    var dateParts = datestring.split("-");
    var day = parseInt(dateParts[0]);
    var month = parseInt(dateParts[1]);
    var year = parseInt(dateParts[2]);
    return new Date(year,month,day);
}

function patientAgeAtAssessment(dob, assessmentDate) {
   var dos = convertDate2(assessmentDate);
    var birthday = convertDate(dob);
    var age =  dos - birthday;
    age  = age/ ( 1000.0 * 3600.0 * 24.0 * 365.0) ;
    var yearsOld = Math.floor(age);
   return yearsOld;
}


function patientAgeAtAssessment2(dob, assessmentDate) {
    var dos = convertDate2(assessmentDate);
    var birthday = convertDate(dob);
    var age = dos.getFullYear() - birthday.getFullYear();
    var m = dos.getMonth() - birthday.getMonth();
    if (m < 0 || (m === 0 && dos.getDate() < birthday.getDate())) {
        age--;
    }

    return age;

}



function getLDL(context) {
   var untreated = context.CDE00013;
   var adjusted = context.LDLCholesterolAdjTreatment;
   var L;

   try {
      L = parseFloat(untreated);
      if ( isNaN(L)) {
        throw new Error("untreated not filled out");
      }
      return L;
   }

   catch (err) {
      try {
         // try adjusted value
         L = parseFloat(adjusted);
         if (! isNaN(L) ){
            return L;
         }
         else {
          return null;
         }
      }

      catch (err2) {
         return null;
      }
    }

}


function getScore(context,patient) {
        var assessmentDate = context.DateOfAssessment;

        var isAdult = patientAgeAtAssessment2(patient.date_of_birth, assessmentDate) >= 18;
        var index = context.CDEIndexOrRelative == "fh_is_index";
        var relative = context.CDEIndexOrRelative == "fh_is_relative";



        var YES = "fh2_y";

        // family history
        var FAM_HIST_PREM_CVD_FIRST_DEGREE_RELATIVE = context.CDE00004;
        var FAM_HIST_HYPERCHOL_FIRST_DEGREE_RELATIVE = context.CDE00003;
        var FAM_HIST_CHILD_HYPERCOL = context.FHFamilyHistoryChild;
        var YES_CHILD = "y_childunder18";
        var FAM_HIST_TENDON_FIRST_DEGREE_RELATIVE = context.FHFamHistTendonXanthoma;
        var FAM_HIST_ARCUS_CORNEALIS_FIRST_DEGREE_RELATIVE = context.FHFamHistArcusCornealis;

        // clinical history
        var PERS_HIST_COR_HEART = context.CDE00011;
        var HAS_COR_HEART_DISEASE = "fhpremcvd_yes_corheartdisease";
        var PERS_HIST_CVD = context.FHPersHistCerebralVD;

        // physical examination
        var TENDON_XANTHOMA = context.CDE00001;
        var ARCUS_CORNEALIS = context.CDE00002;





    function  familyHistoryScore() {
        var score  = 0;

        if ( (FAM_HIST_PREM_CVD_FIRST_DEGREE_RELATIVE  == YES) ||  (FAM_HIST_HYPERCHOL_FIRST_DEGREE_RELATIVE == YES )) {
            score += 1;
        }

        if ( ((FAM_HIST_TENDON_FIRST_DEGREE_RELATIVE == YES) || (FAM_HIST_ARCUS_CORNEALIS_FIRST_DEGREE_RELATIVE == YES))  ||  (FAM_HIST_CHILD_HYPERCOL == YES_CHILD)) {
            score += 2;
        }

        return score;
    }


    function clinicalHistoryScore() {
        var score = 0;

                if ( PERS_HIST_COR_HEART == HAS_COR_HEART_DISEASE) {
                    score += 2;
                }

                if (PERS_HIST_CVD == YES) {
                    score += 1;
                }

                return score;

    }

    function physicalExaminationScore() {
        var score = 0;

        if ( TENDON_XANTHOMA == "y" ) {
                        score += 6;
                }

                if ( ARCUS_CORNEALIS == "y" ) {
                        score += 4;
        }

        return score;
    }

    function investigationScore() {
          var L = getLDL(context);

          if (bad(L)) {
            throw new Error("Please fill in LDL values");
          }

          else {
            var score = 0;

            if ( ( 4.0 <= L ) && ( L < 5.0 )) {
                score += 1;
            }

            // NB the sheet uses <= 6.4 but technically we could have L = 6.45 say
            // whicn using the sheet would give undefined ...
            //add 3 to score if 5.0 <= L <= 6.4
            if ( ( 5.0 <= L ) && ( L < 6.5 )) {
                score += 3;
            }

            //add 5 to score if 6.5 <= L <= 8.4
            if ( (6.5 <= L ) && ( L < 8.5)) {
                score += 5;
            }

            //add 8 to score if L >= 8.5

            if ( L >= 8.5) {
                score += 8;
            }

            return score;
          }
    }

             if (index) {
              console.log("patient is index");
        if (isAdult) {

            try {
                var score = familyHistoryScore() + clinicalHistoryScore() + physicalExaminationScore() + investigationScore();
                return score;
            }

            catch (err) {
                return "";
            }
    }

       else {
        console.log("child - score blank");
        // child  - score not used ( only categorisation )
        return "";
    }
}


else if (relative ) {
    console.log("relative – score blank");
   // relative  - score not used ( only categorisation )
        return "";
    }
}



context.result = getScore(context, patient);


`;

eval("try { " + decodeURIComponent(jscodetoeval) + "} catch (e) {console.log(e);} ");
console.log(eval(jscodetoeval));


// Same code encodededURI - we could use base64, no worries, change it if needed.
// const%20context%20%3D%20%7BmndCuttingFood%3A1%2C%0AmndCuttingFoodWithGastrodtomy%3A1%2C%0AmndSpeech%3A1%2C%0AmndSalivation%3A1%2C%0AmndSwallowing%3A1%2C%0AmndHandwriting%3A1%2C%0AmndDressingHygiene%3A1%2C%0AmndBed%3A1%2C%0AmndWalking%3A1%2C%0AmndClimbingStairs%3A1%2C%0AmndDyspnea%3A1%2C%0AmndOrthopnea%3A1%2C%0AmndRespiratoryInsufficiency%3A1%2C%0A%7D%3B%0A%0Afunction%20bad%28value%29%20%7B%0A%20%20%20return%20%20%28value%20%3D%3D%3D%20null%29%20%7C%7C%20%28%20value%20%3D%3D%3D%20undefined%29%20%7C%7C%20isNaN%28value%29%3B%0A%7D%0A%0Afunction%20getFloat%28x%29%20%7B%0A%20%20%20var%20y%20%3D%20parseFloat%28x%29%3B%0A%20%20%20if%20%28%21%20isNaN%28y%29%29%20%7B%0A%20%20%20%20%20%20%20return%20y%3B%0A%20%20%20%7D%0A%20%20%20return%20null%3B%0A%7D%0A%0Afunction%20getFilledOutScore%28x%2Cy%29%20%7B%0A%20%20%20var%20xval%20%3D%20getFloat%28x%29%3B%0A%20%20%20if%20%28xval%20%21%3D%3D%20null%29%20%7B%0A%20%20%20%20%20%20return%20xval%3B%0A%20%20%20%7D%0A%20%20%20return%20getFloat%28y%29%3B%0A%7D%0A%0Afunction%20getOptionE%28context%29%20%7B%0A%20var%20cutting%20%3D%20%20parseInt%28context.mndCuttingFood%2C%2010%29%3B%0A%20var%20gastrostomy%20%3D%20%20parseInt%28context.mndCuttingFoodWithGastrodtomy%2C%2010%29%3B%0A%20return%20getFilledOutScore%28cutting%2C%20gastrostomy%29%3B%0A%7D%0A%0Avar%20speech%3D%20parseInt%28context.mndSpeech%2C%2010%29%3B%0Avar%20salivation%20%3D%20parseInt%28context.mndSalivation%2C%2010%29%3B%0Avar%20swallowing%20%3D%20%20parseInt%28context.mndSwallowing%2C%2010%29%3B%0Avar%20handwriting%20%3D%20%20parseInt%28context.mndHandwriting%2C%2010%29%3B%0Avar%20hygiene%20%3D%20%20parseInt%28context.mndDressingHygiene%2C%2010%29%3B%0Avar%20bed%20%3D%20%20parseInt%28context.mndBed%2C%2010%29%3B%0Avar%20walking%20%3D%20%20parseInt%28context.mndWalking%2C%2010%29%3B%0Avar%20climbing%20%3D%20%20parseInt%28context.mndClimbingStairs%2C%2010%29%3B%0Avar%20dyspnea%20%3D%20%20parseInt%28context.mndDyspnea%2C%2010%29%3B%0Avar%20orthopnea%20%3D%20%20parseInt%28context.mndOrthopnea%2C%2010%29%3B%0Avar%20respiratory%20%3D%20parseInt%28context.mndRespiratoryInsufficiency%2C%2010%29%3B%0A%0Avar%20cutting_filled%20%3D%20getOptionE%28context%29%3B%0A%0Avar%20total%20%3D%20%28speech%20%2B%20salivation%20%2B%20swallowing%20%2B%20handwriting%20%2B%20cutting_filled%20%2B%20hygiene%20%2B%20bed%20%2B%20walking%20%2B%20climbing%20%2B%20dyspnea%20%2B%20orthopnea%20%2B%20respiratory%29%3B%0A%0Acontext.result%20%3D%20total%3B

app.post('/eval', (req, res) => {
    console.log('Calling eval');

    // console.log(req.body.jscode);
    // console.log(decodeURIComponent(req.body.jscode));
    if (req.body.jscode) {
        console.log()
    }
    console.log(decodeURIComponent(req.body.jscode));
    console.log("Result:");

    const code_to_eval = "try { " + decodeURIComponent(req.body.jscode) + "} catch (e) {console.log(e); res.send(JSON.stringify(\"\"));}";

    console.log(JSON.stringify(eval(code_to_eval)));
    res.send(JSON.stringify(eval(code_to_eval)));

});

app.listen(port, () => console.log(`Example app listening on port ${port}!`));

// handle stop signal so we can close docker container quickly instead to wait for it to kill the node process.
process.on('SIGTERM', () => {
    app.close(() => {
        process.exit(0);
    });
});
