import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.apache.pdfbox.tools.ExtractText;

/**
 * Live oracle probe for the whole ExtractText CLI option surface
 * (org.apache.pdfbox.tools.ExtractText) — the differential-fuzz companion
 * to ExtractTextRangeProbe (which only drives the stripper core).
 *
 * Rather than re-implement ExtractText.call() in the probe, this drives the
 * real upstream class directly: it constructs an ExtractText, sets the same
 * fields the picocli CLI would set from -startPage / -endPage / -sort / -html
 * / -md / -addFileName / -encoding / -console, then invokes the package-private
 * call() (a Callable<Integer>) by reflection so the genuine upstream exit-code
 * + output behaviour is observed. main() can't be used because it routes
 * through picocli and calls System.exit, which would tear down the probe JVM.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> ExtractTextToolFuzzProbe <in.pdf> <outdir> <spec>
 *
 * <spec> is a ';'-separated list of key=value pairs; recognised keys:
 *   start, end           ints (default 1 / Integer.MAX_VALUE)
 *   sort, html, md       "true"/"false" (default false)
 *   addFileName          "true"/"false" (default false)
 *   encoding             charset name (default UTF-8)
 *   console              "true"/"false" (default false; true -> stdout)
 *
 * Output to stdout, UTF-8, no extra framing beyond the two leading lines:
 *   EXIT=<int returned by call()>
 *   ---OUTPUT---
 *   <the extracted text the CLI produced (console capture or outfile bytes)>
 *
 * The probe deliberately fixes outfile to <outdir>/probe.out for the
 * file-output combos so the Python side can read the same bytes; the default-
 * suffix logic (.txt/.html/.md) is exercised separately on the Python side.
 */
public final class ExtractTextToolFuzzProbe {
    public static void main(String[] args) throws Exception {
        File in = new File(args[0]);
        File outdir = new File(args[1]);
        String spec = args[2];

        int start = 1;
        int end = Integer.MAX_VALUE;
        boolean sort = false;
        boolean html = false;
        boolean md = false;
        boolean addFileName = false;
        boolean console = false;
        String encoding = "UTF-8";

        for (String kv : spec.split(";")) {
            if (kv.isEmpty()) {
                continue;
            }
            int eq = kv.indexOf('=');
            String k = kv.substring(0, eq);
            String v = kv.substring(eq + 1);
            switch (k) {
                case "start": start = Integer.parseInt(v); break;
                case "end": end = Integer.parseInt(v); break;
                case "sort": sort = Boolean.parseBoolean(v); break;
                case "html": html = Boolean.parseBoolean(v); break;
                case "md": md = Boolean.parseBoolean(v); break;
                case "addFileName": addFileName = Boolean.parseBoolean(v); break;
                case "console": console = Boolean.parseBoolean(v); break;
                case "encoding": encoding = v; break;
                default: break;
            }
        }

        File outfile = new File(outdir, "probe.out");

        // ExtractText captures System.out into its private SYSOUT field in the
        // constructor and routes BOTH its informational notices and the
        // -console output writer through that captured stream. So the
        // redirect must happen before construction, not just before call().
        PrintStream realOut = System.out;
        ByteArrayOutputStream cap = new ByteArrayOutputStream();
        PrintStream capOut = new PrintStream(cap, true, "UTF-8");
        System.setOut(capOut);

        ExtractText tool = new ExtractText();
        setField(tool, "infile", in);
        setField(tool, "startPage", start);
        setField(tool, "endPage", end);
        setField(tool, "sort", sort);
        setField(tool, "toHTML", html);
        setField(tool, "toMD", md);
        setField(tool, "addFileName", addFileName);
        setField(tool, "encoding", encoding);
        setField(tool, "toConsole", console);
        if (!console) {
            setField(tool, "outfile", outfile);
        }

        // call() returns the int exit code.
        int exit;
        try {
            Method call = ExtractText.class.getDeclaredMethod("call");
            call.setAccessible(true);
            Object rc = call.invoke(tool);
            exit = ((Integer) rc).intValue();
        } finally {
            System.setOut(realOut);
            capOut.flush();
        }

        String body;
        if (console) {
            // The console stream also carries ExtractText's informational
            // notices (SYSOUT shares the same stream). Strip the two known
            // notice lines so the projection is just the extracted text.
            StringBuilder sb = new StringBuilder();
            for (String line : cap.toString("UTF-8").split("\n", -1)) {
                if (line.equals(
                        "The encoding parameter is ignored when writing to the console.")
                        || line.equals(
                        "The encoding parameter is ignored when writing html output.")) {
                    continue;
                }
                if (sb.length() > 0) {
                    sb.append("\n");
                }
                sb.append(line);
            }
            body = sb.toString();
        } else if (outfile.isFile()) {
            body = new String(Files.readAllBytes(outfile.toPath()),
                    java.nio.charset.Charset.forName(encoding));
        } else {
            body = "";
        }

        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        out.println("EXIT=" + exit);
        out.print("---OUTPUT---\n");
        out.print(body);
        out.flush();
    }

    private static void setField(Object obj, String name, Object value) throws Exception {
        Field f = ExtractText.class.getDeclaredField(name);
        f.setAccessible(true);
        if (value instanceof Integer) {
            f.setInt(obj, (Integer) value);
        } else if (value instanceof Boolean) {
            f.setBoolean(obj, (Boolean) value);
        } else {
            f.set(obj, value);
        }
    }
}
