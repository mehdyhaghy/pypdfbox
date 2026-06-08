import java.io.PrintStream;
import java.util.IdentityHashMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThread;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThreadBead;

/** Differential fuzz probe for malformed article thread and bead dictionaries. */
public final class ThreadBeadCycleFuzzProbe {

    private interface Accessor {
        String get();
    }

    private static PrintStream out;

    private static String result(Accessor accessor) {
        try {
            return accessor.get();
        } catch (Throwable throwable) {
            return "ERR:" + throwable.getClass().getSimpleName();
        }
    }

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static void setShape(
            COSDictionary owner, COSName key, String shape, COSBase valid) {
        switch (shape) {
            case "absent":
                return;
            case "null":
                owner.setItem(key, COSNull.NULL);
                return;
            case "wrong":
                owner.setItem(key, COSInteger.ONE);
                return;
            case "direct":
                owner.setItem(key, valid);
                return;
            case "indirect":
                owner.setItem(key, indirect(valid));
                return;
            case "ind_null":
                owner.setItem(key, indirect(COSNull.NULL));
                return;
            case "ind_wrong":
                owner.setItem(key, indirect(COSInteger.ONE));
                return;
            case "nested":
                owner.setItem(key, indirect(indirect(valid)));
                return;
            default:
                throw new IllegalArgumentException(shape);
        }
    }

    private static String dictionaryResult(COSDictionary expected, COSDictionary actual) {
        if (actual == null) {
            return "null";
        }
        return actual == expected ? "same" : "other";
    }

    private static String infoResult(
            COSDictionary expected, PDDocumentInformation info) {
        return info == null
                ? "null"
                : dictionaryResult(expected, info.getCOSObject());
    }

    private static String threadResult(COSDictionary expected, PDThread thread) {
        return thread == null
                ? "null"
                : dictionaryResult(expected, thread.getCOSObject());
    }

    private static String beadResult(COSDictionary expected, PDThreadBead bead) {
        if (bead == null) {
            return "null";
        }
        COSDictionary dictionary = bead.getCOSObject();
        if (dictionary == null) {
            return "wrap:null";
        }
        return dictionaryResult(expected, dictionary);
    }

    private static String pageResult(COSDictionary expected, PDPage page) {
        return page == null
                ? "null"
                : dictionaryResult(expected, page.getCOSObject());
    }

    private static String number(float value) {
        return value == (int) value
                ? Integer.toString((int) value)
                : Float.toString(value);
    }

    private static String rectangleResult(PDRectangle rectangle) {
        if (rectangle == null) {
            return "null";
        }
        return number(rectangle.getLowerLeftX()) + ","
                + number(rectangle.getLowerLeftY()) + ","
                + number(rectangle.getUpperRightX()) + ","
                + number(rectangle.getUpperRightY());
    }

    private static COSArray rectangle(int... values) {
        COSArray array = new COSArray();
        for (int value : values) {
            array.add(COSInteger.get(value));
        }
        return array;
    }

    private static void accessorCases() {
        String[] shapes = {
            "absent", "null", "wrong", "direct", "indirect",
            "ind_null", "ind_wrong", "nested"
        };
        for (String shape : shapes) {
            COSDictionary info = new COSDictionary();
            COSDictionary threadDictionary = new COSDictionary();
            setShape(threadDictionary, COSName.I, shape, info);
            PDThread infoThread = new PDThread(threadDictionary);
            out.println("CASE i_" + shape + " " + result(
                    () -> infoResult(info, infoThread.getThreadInfo())));

            COSDictionary first = new COSDictionary();
            threadDictionary = new COSDictionary();
            setShape(threadDictionary, COSName.F, shape, first);
            PDThread firstThread = new PDThread(threadDictionary);
            out.println("CASE f_" + shape + " " + result(
                    () -> beadResult(first, firstThread.getFirstBead())));

            accessorCase(COSName.T, "t_" + shape, shape, first, "thread");
            accessorCase(COSName.N, "n_" + shape, shape, first, "next");
            accessorCase(COSName.V, "v_" + shape, shape, first, "previous");
            accessorCase(COSName.P, "p_" + shape, shape, first, "page");
        }
    }

    private static void accessorCase(
            COSName key, String name, String shape,
            COSDictionary expected, String accessor) {
        COSDictionary beadDictionary = new COSDictionary();
        setShape(beadDictionary, key, shape, expected);
        PDThreadBead bead = new PDThreadBead(beadDictionary);
        String value;
        switch (accessor) {
            case "thread":
                value = result(() -> threadResult(expected, bead.getThread()));
                break;
            case "next":
                value = result(() -> beadResult(expected, bead.getNextBead()));
                break;
            case "previous":
                value = result(() -> beadResult(expected, bead.getPreviousBead()));
                break;
            case "page":
                value = result(() -> pageResult(expected, bead.getPage()));
                break;
            default:
                throw new IllegalArgumentException(accessor);
        }
        out.println("CASE " + name + " " + value);
    }

    private static void rectangleCases() {
        String[] shapes = {
            "absent", "null", "wrong", "direct", "indirect",
            "ind_null", "ind_wrong", "nested"
        };
        for (String shape : shapes) {
            COSDictionary dictionary = new COSDictionary();
            setShape(dictionary, COSName.R, shape, rectangle(4, 3, 2, 1));
            PDThreadBead bead = new PDThreadBead(dictionary);
            out.println("CASE r_" + shape + " " + result(
                    () -> rectangleResult(bead.getRectangle())));
        }

        COSDictionary shortDictionary = new COSDictionary();
        shortDictionary.setItem(COSName.R, rectangle(7, 8));
        PDThreadBead shortBead = new PDThreadBead(shortDictionary);
        out.println("CASE r_short " + result(
                () -> rectangleResult(shortBead.getRectangle())));

        COSArray badArray = rectangle(1, 2, 3);
        badArray.add(new COSString("x"));
        COSDictionary badDictionary = new COSDictionary();
        badDictionary.setItem(COSName.R, badArray);
        PDThreadBead badBead = new PDThreadBead(badDictionary);
        out.println("CASE r_bad " + result(
                () -> rectangleResult(badBead.getRectangle())));
    }

    private static String link(COSDictionary owner, COSName key,
            COSDictionary first, COSDictionary second) {
        COSBase value = owner.getDictionaryObject(key);
        if (value == null) {
            return "null";
        }
        if (value == first) {
            return "a";
        }
        if (value == second) {
            return "b";
        }
        return "other";
    }

    private static void appendCases() {
        PDThreadBead first = new PDThreadBead();
        PDThreadBead second = new PDThreadBead();
        first.appendBead(second);
        COSDictionary a = first.getCOSObject();
        COSDictionary b = second.getCOSObject();
        out.println("CASE append_two "
                + link(a, COSName.N, a, b) + ","
                + link(a, COSName.V, a, b) + ","
                + link(b, COSName.N, a, b) + ","
                + link(b, COSName.V, a, b));

        COSDictionary bareDictionary = new COSDictionary();
        PDThreadBead bare = new PDThreadBead(bareDictionary);
        PDThreadBead added = new PDThreadBead();
        out.println("CASE append_missing " + result(() -> {
            bare.appendBead(added);
            return link(bareDictionary, COSName.N,
                    bareDictionary, added.getCOSObject());
        }));
    }

    private static String walk(COSDictionary start) {
        IdentityHashMap<COSDictionary, Boolean> seen = new IdentityHashMap<>();
        StringBuilder value = new StringBuilder();
        PDThreadBead current = new PDThreadBead(start);
        for (int index = 0; index < 8; index++) {
            COSDictionary dictionary = current.getCOSObject();
            if (dictionary == null) {
                return value.append(",null").toString();
            }
            if (seen.put(dictionary, Boolean.TRUE) != null) {
                return value.append(",repeat").toString();
            }
            if (value.length() > 0) {
                value.append(',');
            }
            value.append(dictionary == start ? "a" : "b");
            current = current.getNextBead();
        }
        return value.append(",limit").toString();
    }

    private static void cycleCases() {
        COSDictionary self = new COSDictionary();
        self.setItem(COSName.N, self);
        out.println("CASE walk_self " + result(() -> walk(self)));

        COSDictionary first = new COSDictionary();
        COSDictionary second = new COSDictionary();
        first.setItem(COSName.N, second);
        second.setItem(COSName.N, first);
        out.println("CASE walk_two " + result(() -> walk(first)));

        COSDictionary missing = new COSDictionary();
        out.println("CASE walk_missing " + result(() -> walk(missing)));

        COSDictionary wrong = new COSDictionary();
        wrong.setItem(COSName.N, COSInteger.ONE);
        out.println("CASE walk_wrong " + result(() -> walk(wrong)));

        COSDictionary indirectSelf = new COSDictionary();
        indirectSelf.setItem(COSName.N, indirect(indirectSelf));
        out.println("CASE walk_ind_self " + result(() -> walk(indirectSelf)));
    }

    private static void setterCases() {
        PDThread thread = new PDThread();
        PDThreadBead bead = new PDThreadBead();
        thread.setFirstBead(bead);
        out.println("CASE set_first "
                + (thread.getFirstBead().getCOSObject() == bead.getCOSObject())
                + "," + (bead.getThread().getCOSObject() == thread.getCOSObject()));
        thread.setFirstBead(null);
        out.println("CASE clear_first "
                + (thread.getCOSObject().getItem(COSName.F) == null));

        bead.setThread(thread);
        bead.setPage(new PDPage());
        bead.setRectangle(new PDRectangle(1, 2, 3, 4));
        bead.setThread(null);
        bead.setPage(null);
        bead.setRectangle(null);
        out.println("CASE clear_bead "
                + (bead.getCOSObject().getItem(COSName.T) == null) + ","
                + (bead.getCOSObject().getItem(COSName.P) == null) + ","
                + (bead.getCOSObject().getItem(COSName.R) == null));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        accessorCases();
        rectangleCases();
        appendCases();
        cycleCases();
        setterCases();
    }
}
