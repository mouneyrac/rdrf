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

    get(data,key) {
        return data[key];
        // console.log("A function is calling RDRF.get ADSAFE - ignoring...");
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
    'CDE00003': 'fh2_y',
    'FHFamilyHistoryChild': 'fh_n',
    'CDE00004': 'fh2_y',
    'FHFamHistTendonXanthoma': 'fh2_y',
    'FHFamHistArcusCornealis': 'fh2_y',
    'CDE00011': 'fhpremcvd_yes_corheartdisease',
    'FHMyocardialInfarction': '',
    'FHAgeAtMI': '',
    'FHCoronaryRevasc': '',
    'FHAgeAtCV': '',
    'FHPersHistCerebralVD': 'fh2_y',
    'FHAorticValveDisease': '',
    'FHSupravalvularDisease': '',
    'FHPremNonCoronary': '',
    'CDE00001': 'y',
    'CDE00002': 'y',
    'FHXanthelasma': '',
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

function subscript(data, key) {
  // safe access to arrays
  return RDRF.get(data, key);
}

function bad(value) {
    return  (value === null) || ( value === undefined) || isNaN(value);
}

function convertDate(datestring) {
    // use this to on patient demographics dates
    var dateParts = datestring.split("-");
    var day = parseInt(subscript(dateParts, 2), 10);
    var month = parseInt(subscript(dateParts,1), 10);
    var year = parseInt(subscript(dateParts,0), 10);
    return new Date(year,month,day);
}

function convertDate2(datestring) {
    // date values in clinical form parsed this way
    var dateParts = datestring.split("-");
    var day = parseInt(subscript(dateParts,0), 10);
    var month = parseInt(subscript(dateParts,1), 10);
    var year = parseInt(subscript(dateParts,2), 10);
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
        age -= 1;
    }

    return age;

}

function getFloat(x) {
    var y = parseFloat(x);
    if (! isNaN(y)) {
        return y;
    }
    return null;
}

function getFilledOutScore(x,y) {
    var xval = getFloat(x);
    if (xval !== null) {
       return xval;
    }
    return getFloat(y);
 }

function getLDL(context) {
    var untreated = context.CDE00013;
    var adjusted = context.LDLCholesterolAdjTreatment;
    return getFilledOutScore(untreated, adjusted);
}

function catchild(context) {
    // for index patients
    var L = getLDL(context);
    RDRF.log("catchild: L = " + L);

    if (bad(L)) {
        return "";
    }

    function anyrel(context) {
      return ( (context.CDE00003 === "fh2_y") || ( context.CDE00004 === "fh2_y") || ( context.FHFamHistTendonXanthoma === "fh2_y") || ( context.FHFamHistArcusCornealis === "fh2_y" ) );
    }

    //Definite if DNA Analysis is Yes
    //other wise
    if (L > 5.0) {
     return "Highly Probable";
    }

   if ((L >= 4.0) && anyrel(context)) {
     return "Probable";
   }

    if (L >= 4.0) {
      return "Possible";
   }

    return "Unlikely";

}

function catadult(score) {
    // for index patients
    if (bad(score)) {
        return "";
    }

    if (score === "") {
        return "";
    }


    if (score < 3) {
        return "Unlikely";
    }

    if ((3 <= score) && (score <  6)) {
        return "Possible";
    }

    if ((6 <= score) && (score <= 8)) {
       return "Probable";
    }

    return "Definite";
}

function catrelative(sex, age, lipid_score) {
   var table,BIG, MALE_TABLE, FEMALE_TABLE;

    if (bad(lipid_score)) {
        return "";
    }
    RDRF.log("sex = " + sex + " age = " + age + " lipid score = " + lipid_score);
    table = null;
    BIG = 99999999999999.00;
    MALE_TABLE = [
     //  AGE         Unlikely   Uncertain  Likely
     [   [0,14]  , [  [-1,3.099], [3.1,3.499], [3.5, BIG] ]],
     [   [15,24]  , [ [-1,2.999], [3.0,3.499], [3.5, BIG] ]],
     [   [25,34]  , [ [-1,3.799], [3.8,4.599], [4.6, BIG] ]],
     [   [35,44]  , [ [-1,3.999], [4.0,4.799], [4.8, BIG] ]],
     [   [45,54]  , [ [-1,4.399], [4.4,5.299], [5.3, BIG] ]],
     [   [55,999]  ,[ [-1,4.299], [4.3,5.299], [5.3, BIG] ]]];

     FEMALE_TABLE = [
     //  AGE         Unlikely   Uncertain  Likely
     [   [0,14]  , [ [-1,3.399], [3.4,3.799], [3.8, BIG] ]],
     [   [15,24]  , [ [-1,3.299], [3.3,3.899], [3.9, BIG] ]],
     [   [25,34]  , [ [-1,3.599], [3.6,4.299], [4.3, BIG] ]],
     [   [35,44]  , [ [-1,3.699], [3.7,4.399], [4.4, BIG] ]],
     [   [45,54]  , [ [-1,3.999], [4.0,4.899], [4.9, BIG] ]],
     [   [55,999] , [ [-1,4.399], [4.4,5.299], [5.3, BIG] ]]];

     function inRange(value,a,b) {
        return (value >= a) && (value <= b);
     }

     function lookupCat(age, score,table) {
        var row, ageInterval,ageMin,ageMax,catRanges;
        var range, rangeMin, rangeMax, category;
        var cats = ["Unlikely", "Uncertain", "Likely"];
        var i,j;
        for (i=0;i<table.length;i=i+1) {
            row = subscript(table,i);
            ageInterval = subscript(row,0);
            ageMin = subscript(ageInterval,0);
            ageMax = subscript(ageInterval,1);
            if (inRange(age,ageMin,ageMax)) {
                catRanges = subscript(row,1);
                for (j=0;j<3;j=j+1) {
                    RDRF.log("checking " + subscript(cats,j));
                    range = subscript(catRanges,j);
                    rangeMin = subscript(range,0);
                    rangeMax = subscript(range,1);

                    RDRF.log("min = " + rangeMin);
                    RDRF.log("max = " + rangeMax);


                    if (inRange(score,rangeMin, rangeMax)) {
                        category = subscript(cats,j);
                        RDRF.log("in range!");
                        return category;
                    }
                }
            }
        }

        RDRF.log("age = " + age + " score = " + score + " no cat?!");
        return "";

     }


    if (sex === '1') {
        table = MALE_TABLE;
    }

    if (sex === '2') {
        table = FEMALE_TABLE;
    }

    if (table === null) {
        return "";
    }

    return lookupCat(age, lipid_score, table);
 }

function categorise(context,patient) {
  var dutch_lipid_network_score = context.CDEfhDutchLipidClinicNetwork;
  var assessmentDate = context.DateOfAssessment;
  var isAdult = patientAgeAtAssessment2(patient.date_of_birth, assessmentDate) >= 18.0;
  var index = context.CDEIndexOrRelative === "fh_is_index";
  var relative = context.CDEIndexOrRelative === "fh_is_relative";
  var age, L, sex, cr;

  if (index) {
    RDRF.log("patient is index");
    if (isAdult) {
        RDRF.log("patient is an adult");
        return catadult(dutch_lipid_network_score);
    }

    RDRF.log("patient is a child");
    return catchild(context);

  }

  if (relative ) {
    RDRF.log("patient is a relative");
    age = patientAgeAtAssessment2(patient.date_of_birth, assessmentDate);
    L = getLDL(context);
    sex = patient.sex;
    cr = catrelative(sex, age, L);
    RDRF.log("cat relative = " + cr);
    return cr;
  }
}

context.result = categorise(context, patient);



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
