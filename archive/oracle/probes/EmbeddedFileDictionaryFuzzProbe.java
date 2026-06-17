import java.io.PrintStream;
import java.util.Calendar;
import java.util.Locale;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.filespecification.PDComplexFileSpecification;
import org.apache.pdfbox.pdmodel.common.filespecification.PDEmbeddedFile;

/** Accessor-level malformed dictionary oracle for wave 1520, agent D. */
public final class EmbeddedFileDictionaryFuzzProbe {
    private static final String[] CASE_IDS = {
        "ef-0", "ef-n", "ef-z", "ef-iz", "ef-e", "ef-fd", "ef-fs", "ef-fi",
        "ef-all", "ef-bad", "p-0", "p-n", "p-z", "p-iz", "p-e", "p-i",
        "sz-i", "sz-f", "sz-w", "sz-s", "sz-n", "sz-ii", "sz-iz",
        "dt-v", "dt-p", "dt-np", "dt-z", "dt-bad", "dt-roll", "dt-n", "dt-i",
        "cs-s", "cs-n", "cs-i", "cs-z", "st-n", "st-s", "st-i", "st-z",
        "mac-v", "mac-i", "mac-n", "mac-bad", "mac-z"
    };

    private static final COSName EF = COSName.getPDFName("EF");
    private static final COSName F = COSName.getPDFName("F");
    private static final COSName UF = COSName.getPDFName("UF");
    private static final COSName DOS = COSName.getPDFName("DOS");
    private static final COSName MAC = COSName.getPDFName("Mac");
    private static final COSName UNIX = COSName.getPDFName("Unix");
    private static final COSName PARAMS = COSName.getPDFName("Params");
    private static final COSName SIZE = COSName.getPDFName("Size");
    private static final COSName CREATION_DATE = COSName.getPDFName("CreationDate");
    private static final COSName MOD_DATE = COSName.getPDFName("ModDate");
    private static final COSName CHECK_SUM = COSName.getPDFName("CheckSum");
    private static final COSName SUBTYPE = COSName.getPDFName("Subtype");
    private static final COSName CREATOR = COSName.getPDFName("Creator");
    private static final COSName RES_FORK = COSName.getPDFName("ResFork");

    private EmbeddedFileDictionaryFuzzProbe() {}

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSStream stream() {
        COSStream stream = new COSStream();
        stream.setItem(COSName.TYPE, COSName.EMBEDDED_FILE);
        return stream;
    }

    private static COSDictionary params(COSStream stream) {
        COSDictionary params = new COSDictionary();
        stream.setItem(PARAMS, params);
        return params;
    }

    private static PDComplexFileSpecification build(String caseId) {
        COSDictionary fileSpec = new COSDictionary();
        COSDictionary ef = new COSDictionary();
        COSStream embedded = stream();
        COSDictionary values;

        switch (caseId) {
            case "ef-0":
                return new PDComplexFileSpecification(fileSpec);
            case "ef-n":
                fileSpec.setItem(EF, COSName.getPDFName("Wrong"));
                return new PDComplexFileSpecification(fileSpec);
            case "ef-z":
                fileSpec.setItem(EF, COSNull.NULL);
                return new PDComplexFileSpecification(fileSpec);
            case "ef-iz":
                fileSpec.setItem(EF, indirect(null));
                return new PDComplexFileSpecification(fileSpec);
            case "ef-e":
                fileSpec.setItem(EF, ef);
                return new PDComplexFileSpecification(fileSpec);
            case "ef-fd":
                ef.setItem(F, new COSDictionary());
                break;
            case "ef-fs":
                ef.setItem(F, embedded);
                break;
            case "ef-fi":
                ef.setItem(F, indirect(embedded));
                break;
            case "ef-all":
                ef.setItem(F, stream());
                ef.setItem(UF, indirect(stream()));
                ef.setItem(DOS, stream());
                ef.setItem(MAC, indirect(stream()));
                ef.setItem(UNIX, stream());
                break;
            case "ef-bad":
                ef.setItem(F, COSName.getPDFName("Wrong"));
                ef.setItem(UF, COSNull.NULL);
                ef.setItem(DOS, indirect(null));
                ef.setItem(MAC, new COSDictionary());
                ef.setItem(UNIX, COSInteger.ONE);
                break;
            default:
                ef.setItem(F, embedded);
                switch (caseId) {
                    case "p-0":
                        break;
                    case "p-n":
                        embedded.setItem(PARAMS, COSName.getPDFName("Wrong"));
                        break;
                    case "p-z":
                        embedded.setItem(PARAMS, COSNull.NULL);
                        break;
                    case "p-iz":
                        embedded.setItem(PARAMS, indirect(null));
                        break;
                    case "p-e":
                        params(embedded);
                        break;
                    case "p-i":
                        embedded.setItem(PARAMS, indirect(new COSDictionary()));
                        break;
                    case "sz-i":
                        params(embedded).setItem(SIZE, COSInteger.get(42));
                        break;
                    case "sz-f":
                        params(embedded).setItem(SIZE, new COSFloat(3.75f));
                        break;
                    case "sz-w":
                        params(embedded).setItem(SIZE, COSInteger.get(4294967297L));
                        break;
                    case "sz-s":
                        params(embedded).setItem(SIZE, new COSString("42"));
                        break;
                    case "sz-n":
                        params(embedded).setItem(SIZE, COSName.getPDFName("FortyTwo"));
                        break;
                    case "sz-ii":
                        params(embedded).setItem(SIZE, indirect(COSInteger.get(42)));
                        break;
                    case "sz-iz":
                        params(embedded).setItem(SIZE, indirect(null));
                        break;
                    case "dt-v":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("D:20240102030405+06'30'"));
                        values.setItem(MOD_DATE, new COSString("D:20231231235958-04'15'"));
                        break;
                    case "dt-p":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("D:2024"));
                        values.setItem(MOD_DATE, new COSString("D:202402"));
                        break;
                    case "dt-np":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("20240102"));
                        values.setItem(MOD_DATE, new COSString("20240102030405Z"));
                        break;
                    case "dt-z":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("D:20240102030405Z"));
                        values.setItem(MOD_DATE, COSNull.NULL);
                        break;
                    case "dt-bad":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("garbage"));
                        values.setItem(MOD_DATE, new COSString("D:99999999"));
                        break;
                    case "dt-roll":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, new COSString("D:20241301000000"));
                        values.setItem(MOD_DATE, new COSString("D:20240230000000"));
                        break;
                    case "dt-n":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, COSName.getPDFName("D:20240101"));
                        values.setItem(MOD_DATE, COSInteger.ONE);
                        break;
                    case "dt-i":
                        values = params(embedded);
                        values.setItem(CREATION_DATE, indirect(new COSString("D:20240102")));
                        values.setItem(MOD_DATE, indirect(new COSString("D:20240103")));
                        break;
                    case "cs-s":
                        params(embedded).setItem(CHECK_SUM, new COSString("abc123"));
                        break;
                    case "cs-n":
                        params(embedded).setItem(CHECK_SUM, COSName.getPDFName("abc123"));
                        break;
                    case "cs-i":
                        params(embedded).setItem(CHECK_SUM, indirect(new COSString("abc123")));
                        break;
                    case "cs-z":
                        params(embedded).setItem(CHECK_SUM, COSNull.NULL);
                        break;
                    case "st-n":
                        embedded.setItem(SUBTYPE, COSName.getPDFName("application/pdf"));
                        break;
                    case "st-s":
                        embedded.setItem(SUBTYPE, new COSString("text/plain"));
                        break;
                    case "st-i":
                        embedded.setItem(SUBTYPE, indirect(new COSString("image/png")));
                        break;
                    case "st-z":
                        embedded.setItem(SUBTYPE, COSNull.NULL);
                        break;
                    case "mac-v":
                        values = new COSDictionary();
                        values.setItem(SUBTYPE, new COSString("TEXT"));
                        values.setItem(CREATOR, new COSString("ttxt"));
                        values.setItem(RES_FORK, new COSString("fork"));
                        params(embedded).setItem(MAC, values);
                        break;
                    case "mac-i":
                        values = new COSDictionary();
                        values.setItem(SUBTYPE, indirect(new COSString("TEXT")));
                        values.setItem(CREATOR, indirect(new COSString("ttxt")));
                        values.setItem(RES_FORK, indirect(new COSString("fork")));
                        params(embedded).setItem(MAC, indirect(values));
                        break;
                    case "mac-n":
                        values = new COSDictionary();
                        values.setItem(SUBTYPE, COSName.getPDFName("TEXT"));
                        values.setItem(CREATOR, COSName.getPDFName("ttxt"));
                        values.setItem(RES_FORK, COSName.getPDFName("fork"));
                        params(embedded).setItem(MAC, values);
                        break;
                    case "mac-bad":
                        params(embedded).setItem(MAC, COSInteger.ONE);
                        break;
                    case "mac-z":
                        params(embedded).setItem(MAC, indirect(null));
                        break;
                    default:
                        throw new IllegalArgumentException(caseId);
                }
                break;
        }
        fileSpec.setItem(EF, ef);
        return new PDComplexFileSpecification(fileSpec);
    }

    private static String value(String value) {
        return value == null ? "null" : value;
    }

    private static String date(Calendar calendar) {
        if (calendar == null) {
            return "null";
        }
        int offsetMinutes = calendar.getTimeZone().getOffset(calendar.getTimeInMillis()) / 60000;
        return String.format(
                Locale.ROOT,
                "%04d%02d%02d%02d%02d%02d@%d",
                calendar.get(Calendar.YEAR),
                calendar.get(Calendar.MONTH) + 1,
                calendar.get(Calendar.DAY_OF_MONTH),
                calendar.get(Calendar.HOUR_OF_DAY),
                calendar.get(Calendar.MINUTE),
                calendar.get(Calendar.SECOND),
                offsetMinutes);
    }

    private static String call(StringCall call) {
        try {
            return value(call.get());
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String dateCall(DateCall call) {
        try {
            return date(call.get());
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String slot(FileCall call) {
        try {
            return call.get() == null ? "0" : "1";
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String project(String caseId) {
        PDComplexFileSpecification fileSpec = build(caseId);
        String slots = String.join(
                "",
                slot(fileSpec::getEmbeddedFile),
                slot(fileSpec::getEmbeddedFileUnicode),
                slot(fileSpec::getEmbeddedFileDos),
                slot(fileSpec::getEmbeddedFileMac),
                slot(fileSpec::getEmbeddedFileUnix));
        PDEmbeddedFile embedded;
        try {
            embedded = fileSpec.getEmbeddedFile();
        } catch (Exception exception) {
            return "CASE " + caseId + " slots=" + slots + " ef=ERR:"
                    + exception.getClass().getSimpleName();
        }
        if (embedded == null) {
            return "CASE " + caseId + " slots=" + slots + " ef=null";
        }
        String size;
        try {
            size = Integer.toString(embedded.getSize());
        } catch (Exception exception) {
            size = "ERR:" + exception.getClass().getSimpleName();
        }
        return "CASE " + caseId
                + " slots=" + slots
                + " ef=stream"
                + " sub=" + call(embedded::getSubtype)
                + " size=" + size
                + " cd=" + dateCall(embedded::getCreationDate)
                + " md=" + dateCall(embedded::getModDate)
                + " sum=" + call(embedded::getCheckSum)
                + " macsub=" + call(embedded::getMacSubtype)
                + " maccreator=" + call(embedded::getMacCreator)
                + " macres=" + call(embedded::getMacResFork);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String caseId : CASE_IDS) {
            out.println(project(caseId));
        }
    }

    private interface StringCall {
        String get() throws Exception;
    }

    private interface DateCall {
        Calendar get() throws Exception;
    }

    private interface FileCall {
        PDEmbeddedFile get() throws Exception;
    }
}
