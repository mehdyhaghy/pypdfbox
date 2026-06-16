import java.io.PrintStream;
import java.util.Calendar;
import java.util.Set;
import java.util.TreeSet;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;

/**
 * Differential fuzz probe for {@link PDDocumentInformation} (the trailer
 * {@code /Info} dictionary) exercised IN-MEMORY over a directly-constructed
 * {@code COSDictionary}, plus SET/GET round-trips — Apache PDFBox 3.0.7
 * (wave 1549, agent E).
 *
 * <p>Deliberately distinct from the file-based read-only
 * {@code DocInfoFuzzProbe} (wave 1516): that one saves a one-page PDF whose
 * trailer Info dict is the fuzzed dict and reloads it, so save/reload
 * normalises the raw COSString date and name forms. This probe wraps
 * {@code new PDDocumentInformation(cosDict)} with no round-trip — testing the
 * wrapper layer directly — AND exercises the mutating setters
 * ({@code setTitle}, {@code setCreationDate}, {@code setTrapped},
 * {@code setCustomMetadataValue}) and re-reads the result.
 *
 * <p>Fuzz angles NOT covered by wave 1516:
 * <ul>
 *   <li>direct in-memory construction (no save/reload) so a COSString that
 *       happens to be a valid date string is read exactly as stored;</li>
 *   <li>full string-field surface — subject / keywords / creator (1516 only
 *       projected title / author / producer);</li>
 *   <li>rich {@code /CreationDate} / {@code /ModDate} variants: negative TZ
 *       offset, {@code Z} suffix, GMT-prefixed offset, ISO-8601, year-only,
 *       year-month, leading/trailing whitespace, lowercase {@code d:} prefix;</li>
 *   <li>set/get round-trips: setTitle(x)->getTitle, setCreationDate(cal)->
 *       getCreationDate (millis), setTrapped("True")->getTrapped,
 *       setCustomMetadataValue->getCustomMetadataValue, setTitle(null) clears;</li>
 *   <li>setTrapped("garbage") exception parity (Java IllegalArgumentException
 *       vs Python ValueError, both projected as ERR:&lt;type&gt;).</li>
 * </ul>
 *
 * <p>Each case is built and projected entirely in this process (and mirrored
 * exactly in the Python sibling); there is no on-disk corpus. Output is one
 * framed line per case, in a fixed order.
 *
 * <p>Line grammar:
 *
 * <pre>
 *   CASE &lt;name&gt; title=&lt;v&gt; author=&lt;v&gt; subject=&lt;v&gt; keywords=&lt;v&gt; creator=&lt;v&gt; producer=&lt;v&gt; cdate=&lt;millis|null|ERR&gt; mdate=&lt;millis|null|ERR&gt; trapped=&lt;v&gt; keys=&lt;k,k|-&gt; custom_X=&lt;v&gt;
 * </pre>
 *
 * where each {@code v} is the string value, {@code null}, or
 * {@code ERR:SimpleName}.
 */
public final class DocumentInfoFuzzProbe {

    static PrintStream out;

    static String exc(Exception e) {
        // Java IllegalArgumentException <-> Python ValueError: normalise both
        // to ERR:IllegalArgument so the cross-language exception compares.
        String n = e.getClass().getSimpleName();
        if ("IllegalArgumentException".equals(n)) {
            return "ERR:IllegalArgument";
        }
        return "ERR:" + n;
    }

    static String s(String v) {
        return v == null ? "null" : v;
    }

    static COSName n(String name) {
        return COSName.getPDFName(name);
    }

    static String date(Calendar c) {
        return c == null ? "null" : Long.toString(c.getTimeInMillis());
    }

    // ---- per-case Info dict builders (mirror the Python sibling exactly) ----

    static COSDictionary build(String name) {
        COSDictionary d = new COSDictionary();
        switch (name) {
            case "bare":
                break;
            // ---- every standard string field as spec COSString ----
            case "all_strings":
                d.setItem(n("Title"), new COSString("T"));
                d.setItem(n("Author"), new COSString("A"));
                d.setItem(n("Subject"), new COSString("S"));
                d.setItem(n("Keywords"), new COSString("K"));
                d.setItem(n("Creator"), new COSString("C"));
                d.setItem(n("Producer"), new COSString("P"));
                break;
            // ---- string fields as a NAME (getString rejects -> null) ----
            case "subject_is_name":
                d.setItem(n("Subject"), n("S"));
                break;
            case "keywords_is_number":
                d.setItem(n("Keywords"), COSInteger.get(5));
                break;
            case "creator_is_array":
                d.setItem(n("Creator"), new COSArray());
                break;
            case "title_empty_string":
                d.setItem(n("Title"), new COSString(""));
                break;
            case "title_unicode":
                d.setItem(n("Title"), new COSString("café ☃"));
                break;
            // ---- date variants ----
            case "cdate_pos_offset":
                d.setItem(n("CreationDate"),
                        new COSString("D:20240101120000+05'00'"));
                break;
            case "cdate_neg_offset":
                d.setItem(n("CreationDate"),
                        new COSString("D:20240101120000-08'30'"));
                break;
            case "cdate_z_suffix":
                d.setItem(n("CreationDate"),
                        new COSString("D:20240101120000Z"));
                break;
            case "cdate_zero_offset_apos":
                d.setItem(n("CreationDate"),
                        new COSString("D:20240101120000+00'00'"));
                break;
            case "cdate_year_only":
                d.setItem(n("CreationDate"), new COSString("D:2024"));
                break;
            case "cdate_year_month":
                d.setItem(n("CreationDate"), new COSString("D:202406"));
                break;
            case "cdate_ymd":
                d.setItem(n("CreationDate"), new COSString("D:20240615"));
                break;
            case "cdate_no_prefix_z":
                d.setItem(n("CreationDate"),
                        new COSString("20240101120000Z"));
                break;
            case "cdate_iso8601":
                d.setItem(n("CreationDate"),
                        new COSString("2024-03-15T12:00:00Z"));
                break;
            case "cdate_leading_ws":
                d.setItem(n("CreationDate"),
                        new COSString("  D:20240101120000Z"));
                break;
            case "cdate_lower_prefix":
                d.setItem(n("CreationDate"),
                        new COSString("d:20240101120000Z"));
                break;
            case "cdate_garbage":
                d.setItem(n("CreationDate"), new COSString("xyz"));
                break;
            case "cdate_is_number":
                d.setItem(n("CreationDate"), COSInteger.get(20240101L));
                break;
            case "mdate_pos_offset":
                d.setItem(n("ModDate"),
                        new COSString("D:19991231235959+02'00'"));
                break;
            // ---- trapped ----
            case "trapped_true_name":
                d.setItem(n("Trapped"), n("True"));
                break;
            case "trapped_false_name":
                d.setItem(n("Trapped"), n("False"));
                break;
            case "trapped_unknown_name":
                d.setItem(n("Trapped"), n("Unknown"));
                break;
            case "trapped_string":
                d.setItem(n("Trapped"), new COSString("True"));
                break;
            case "trapped_bogus_name":
                d.setItem(n("Trapped"), n("Sometimes"));
                break;
            case "trapped_number":
                d.setItem(n("Trapped"), COSInteger.get(1));
                break;
            // ---- custom keys ----
            case "custom_mix":
                d.setItem(n("Title"), new COSString("T"));
                d.setItem(n("Foo"), new COSString("bar"));
                d.setItem(n("Zeta"), new COSString("z"));
                d.setItem(n("Alpha"), new COSString("a"));
                break;
            case "custom_value_number":
                d.setItem(n("Foo"), COSInteger.get(7));
                break;
            default:
                break;
        }
        return d;
    }

    // ---- mutators: applied after construction to exercise the setters ----

    static void mutate(PDDocumentInformation info, String name) {
        switch (name) {
            case "set_title_roundtrip":
                info.setTitle("Hello");
                break;
            case "set_title_then_clear":
                info.setTitle("Hello");
                info.setTitle(null);
                break;
            case "set_creationdate_roundtrip": {
                Calendar c = Calendar.getInstance(
                        java.util.TimeZone.getTimeZone("GMT+05:00"));
                c.clear();
                c.set(2022, Calendar.JUNE, 1, 9, 30, 0);
                info.setCreationDate(c);
                break;
            }
            case "set_trapped_true_roundtrip":
                info.setTrapped("True");
                break;
            case "set_trapped_garbage":
                info.setTrapped("garbage");
                break;
            case "set_custom_roundtrip":
                info.setCustomMetadataValue("MyKey", "MyVal");
                break;
            case "set_custom_then_null":
                info.setCustomMetadataValue("MyKey", "MyVal");
                info.setCustomMetadataValue("MyKey", null);
                break;
            default:
                break;
        }
    }

    static String customField(String name) {
        // which custom key each case probes via getCustomMetadataValue
        switch (name) {
            case "custom_mix":
            case "custom_value_number":
                return "Foo";
            case "set_custom_roundtrip":
            case "set_custom_then_null":
                return "MyKey";
            default:
                return "Foo";
        }
    }

    static String call(java.util.concurrent.Callable<String> f) {
        try {
            return s(f.call());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static void runCase(String name) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        try {
            COSDictionary dict = build(name);
            PDDocumentInformation info = new PDDocumentInformation(dict);
            // a mutator may throw (setTrapped garbage) -> capture as the
            // trapped cell; mark the rest as the post-mutation state.
            String mutErr = null;
            try {
                mutate(info, name);
            } catch (Exception e) {
                mutErr = exc(e);
            }
            sb.append("title=").append(call(info::getTitle));
            sb.append(" author=").append(call(info::getAuthor));
            sb.append(" subject=").append(call(info::getSubject));
            sb.append(" keywords=").append(call(info::getKeywords));
            sb.append(" creator=").append(call(info::getCreator));
            sb.append(" producer=").append(call(info::getProducer));
            sb.append(" cdate=").append(call(() -> date(info.getCreationDate())));
            sb.append(" mdate=")
                    .append(call(() -> date(info.getModificationDate())));
            sb.append(" trapped=");
            if (mutErr != null) {
                sb.append(mutErr);
            } else {
                sb.append(call(info::getTrapped));
            }
            sb.append(" keys=").append(call(() -> {
                Set<String> ks = new TreeSet<>(info.getMetadataKeys());
                return ks.isEmpty() ? "-" : String.join(",", ks);
            }));
            sb.append(" custom_X=").append(call(
                    () -> info.getCustomMetadataValue(customField(name))));
        } catch (Exception e) {
            sb.append("BUILD:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        for (String name : CASES) {
            runCase(name);
        }
    }

    // Fixed case order — mirrored verbatim in the Python sibling.
    static final String[] CASES = {
        "bare",
        "all_strings",
        "subject_is_name",
        "keywords_is_number",
        "creator_is_array",
        "title_empty_string",
        "title_unicode",
        "cdate_pos_offset",
        "cdate_neg_offset",
        "cdate_z_suffix",
        "cdate_zero_offset_apos",
        "cdate_year_only",
        "cdate_year_month",
        "cdate_ymd",
        "cdate_no_prefix_z",
        "cdate_iso8601",
        "cdate_leading_ws",
        "cdate_lower_prefix",
        "cdate_garbage",
        "cdate_is_number",
        "mdate_pos_offset",
        "trapped_true_name",
        "trapped_false_name",
        "trapped_unknown_name",
        "trapped_string",
        "trapped_bogus_name",
        "trapped_number",
        "custom_mix",
        "custom_value_number",
        "set_title_roundtrip",
        "set_title_then_clear",
        "set_creationdate_roundtrip",
        "set_trapped_true_roundtrip",
        "set_trapped_garbage",
        "set_custom_roundtrip",
        "set_custom_then_null",
    };
}
