import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocumentNameDestinationDictionary;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;

/**
 * Differential fuzz probe for the catalog {@code /Names} subtree wrappers,
 * Apache PDFBox 3.0.7 (wave 1555, agent B). Complements the sibling
 * DocumentNameDictionaryFuzzProbe (wave 1529) — which drives the
 * {@link PDDocumentNameDictionary} accessor leniency over a MALFORMED
 * {@code /Names} sub-dictionary via on-disk PDFs — by attacking two surfaces
 * that probe does NOT touch:
 *
 * <ol>
 *   <li><b>Per-name destination resolution</b> on the legacy flat
 *       {@link PDDocumentNameDestinationDictionary} ({@code getDestination(name)}
 *       over ~20 malformed / edge entry values). This is the
 *       "named-destination resolution returning a page destination vs null vs
 *       exception" surface, exercised directly against the wrapper (no catalog
 *       traversal), so the value-shape matrix is exhaustively pinned.</li>
 *   <li><b>Sub-entry accessor presence/class</b> on
 *       {@link PDDocumentNameDictionary} built directly over an in-memory
 *       {@code /Names} dict whose every upstream-exposed sub-entry
 *       ({@code /Dests} {@code /EmbeddedFiles} {@code /JavaScript}) is set
 *       present-as-dict vs present-as-non-dict vs missing, plus a sample
 *       {@code getDests().getDestination(name)} lookup chained through the
 *       name-tree wrapper.</li>
 * </ol>
 *
 * <p>Built entirely in-memory (no file round-trip needed — the wrappers accept a
 * raw {@code COSDictionary}), so this probe takes no arguments. The pypdfbox
 * sibling (tests/pdmodel/oracle/test_name_dictionary_fuzz_wave1555.py)
 * constructs the byte-identical COS shapes and projects the identical grammar.
 *
 * <p>Output is two framed sections, LF-terminated lines, UTF-8:
 *
 * <pre>
 *   GETDEST &lt;case&gt; = &lt;cls|null|ERR:&lt;ExcSimpleName&gt;&gt;
 *   NAMEDICT &lt;case&gt; dests=&lt;...&gt; embed=&lt;...&gt; js=&lt;...&gt; deslookup=&lt;...&gt;
 * </pre>
 *
 * <p>Java is ground truth. {@code IOException} maps to pypdfbox {@code OSError}
 * per the harness convention. A real divergence is a production fix; a
 * defensible one is pinned with a CHANGES.md row.
 */
public final class NameDictionaryFuzzProbe {

    static PrintStream out;

    static String cls(Object o) {
        return o == null ? "null" : o.getClass().getSimpleName();
    }

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static COSArray xyz() {
        COSArray a = new COSArray();
        a.add(COSInteger.get(0));
        a.add(COSName.getPDFName("XYZ"));
        a.add(COSInteger.get(1));
        a.add(COSInteger.get(2));
        a.add(COSInteger.get(3));
        return a;
    }

    static COSArray fit() {
        COSArray a = new COSArray();
        a.add(COSInteger.get(0));
        a.add(COSName.getPDFName("Fit"));
        return a;
    }

    static COSDictionary wrapD(COSBase d) {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.getPDFName("D"), d);
        return dict;
    }

    static String getDest(PDDocumentNameDestinationDictionary dd, String name) {
        try {
            return cls(dd.getDestination(name));
        } catch (Exception e) {
            return exc(e);
        }
    }

    // -------------------- section 1: flat /Dests getDestination --------------------

    static void destSection() {
        COSDictionary d = new COSDictionary();

        // bare explicit-destination arrays
        d.setItem(COSName.getPDFName("arr_xyz"), xyz());
        d.setItem(COSName.getPDFName("arr_fit"), fit());

        // {/D <array>} dict forms
        d.setItem(COSName.getPDFName("dictD_xyz"), wrapD(xyz()));
        d.setItem(COSName.getPDFName("dictD_fit"), wrapD(fit()));

        // {/D <string>} and {/D <name>}: named-dest chain (create() accepts both)
        d.setItem(COSName.getPDFName("dictD_str"), wrapD(new COSString("target")));
        d.setItem(COSName.getPDFName("dictD_name"), wrapD(COSName.getPDFName("target")));

        // {/D <dict>} : /D resolves to a non-array/non-string -> create() error
        d.setItem(COSName.getPDFName("dictD_dict"), wrapD(new COSDictionary()));

        // {/D <short array>} : array too short -> create() error
        COSArray sa = new COSArray();
        sa.add(COSInteger.get(0));
        d.setItem(COSName.getPDFName("dictD_shortarr"), wrapD(sa));

        // dict WITHOUT /D : getDestination returns null (no array, no /D)
        COSDictionary noD = new COSDictionary();
        noD.setItem(COSName.getPDFName("Type"), COSName.getPDFName("X"));
        d.setItem(COSName.getPDFName("dict_noD"), noD);

        // bare wrong-typed values: null (not array, not dict-with-/D)
        d.setItem(COSName.getPDFName("bare_name"), COSName.getPDFName("foo"));
        d.setItem(COSName.getPDFName("bare_string"), new COSString("foo"));
        d.setItem(COSName.getPDFName("bare_number"), COSInteger.get(5));

        // malformed bare arrays -> create() error
        COSArray shortArr = new COSArray();
        shortArr.add(COSInteger.get(0));
        d.setItem(COSName.getPDFName("arr_short"), shortArr);
        d.setItem(COSName.getPDFName("arr_empty"), new COSArray());
        COSArray badItem1 = new COSArray();
        badItem1.add(COSInteger.get(0));
        badItem1.add(COSInteger.get(9)); // item[1] not a name
        d.setItem(COSName.getPDFName("arr_baditem1"), badItem1);
        COSArray unknownFit = new COSArray();
        unknownFit.add(COSInteger.get(0));
        unknownFit.add(COSName.getPDFName("BOGUS")); // unknown fit type
        d.setItem(COSName.getPDFName("arr_unknownfit"), unknownFit);

        PDDocumentNameDestinationDictionary dd =
                new PDDocumentNameDestinationDictionary(d);

        String[] cases = {
            "arr_xyz", "arr_fit", "dictD_xyz", "dictD_fit", "dictD_str",
            "dictD_name", "dictD_dict", "dictD_shortarr", "dict_noD",
            "bare_name", "bare_string", "bare_number", "arr_short",
            "arr_empty", "arr_baditem1", "arr_unknownfit", "absent",
        };
        for (String c : cases) {
            out.println("GETDEST " + c + " = " + getDest(dd, c));
        }
    }

    // -------------------- section 2: /Names accessor leniency --------------------

    static String dests(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getDests());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String embed(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getEmbeddedFiles());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String js(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getJavaScript());
        } catch (Exception e) {
            return exc(e);
        }
    }

    // getDests() returns a PDDestinationNameTreeNode (the name-tree wrapper);
    // resolve a sample name through it. A flat /Dests dict carrying a "home"
    // explicit-destination array is exposed as a single-node name tree whose
    // /Names array would be absent, so getValue("home") returns null here —
    // pinning that the name-tree wrapper does NOT treat the flat dict's keys as
    // name-tree leaves.
    static String desLookup(PDDocumentNameDictionary nd) {
        try {
            org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode t = nd.getDests();
            if (t == null) {
                return "null";
            }
            return cls(t.getValue("home"));
        } catch (Exception e) {
            return exc(e);
        }
    }

    static COSDictionary namesWith(String key, COSBase value) {
        COSDictionary names = new COSDictionary();
        if (value != null) {
            names.setItem(COSName.getPDFName(key), value);
        }
        return names;
    }

    static void nameDictSection() {
        // each upstream-exposed sub-entry present-as-dict vs non-dict vs missing
        COSDictionary allDicts = new COSDictionary();
        allDicts.setItem(COSName.getPDFName("Dests"), new COSDictionary());
        allDicts.setItem(COSName.getPDFName("EmbeddedFiles"), new COSDictionary());
        allDicts.setItem(COSName.getPDFName("JavaScript"), new COSDictionary());

        COSDictionary allNonDict = new COSDictionary();
        allNonDict.setItem(COSName.getPDFName("Dests"), COSName.getPDFName("x"));
        allNonDict.setItem(COSName.getPDFName("EmbeddedFiles"), new COSArray());
        allNonDict.setItem(COSName.getPDFName("JavaScript"), new COSString("x"));

        // a /Dests name-tree with a real /Names leaf array carrying "home"
        COSDictionary destTree = new COSDictionary();
        COSArray namesArr = new COSArray();
        namesArr.add(new COSString("home"));
        namesArr.add(xyz());
        destTree.setItem(COSName.getPDFName("Names"), namesArr);
        COSDictionary namesDestTree = new COSDictionary();
        namesDestTree.setItem(COSName.getPDFName("Dests"), destTree);

        String[] labels = {
            "empty", "all_dicts", "all_nondict", "dests_only_dict",
            "dests_only_nondict", "dests_nametree_home",
        };
        COSDictionary[] dicts = {
            new COSDictionary(),
            allDicts,
            allNonDict,
            namesWith("Dests", new COSDictionary()),
            namesWith("Dests", COSInteger.get(3)),
            namesDestTree,
        };
        for (int i = 0; i < labels.length; i++) {
            PDDocumentNameDictionary nd = new PDDocumentNameDictionary(null, dicts[i]);
            out.println("NAMEDICT " + labels[i]
                    + " dests=" + dests(nd)
                    + " embed=" + embed(nd)
                    + " js=" + js(nd)
                    + " deslookup=" + desLookup(nd));
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        destSection();
        nameDictSection();
    }
}
