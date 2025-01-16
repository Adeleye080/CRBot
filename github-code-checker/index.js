import dotenv from "dotenv";
import express from "express";
import bodyParser from "body-parser";
import axios from "axios";
import jwt from "jsonwebtoken";
import crypto from "crypto";
import { exec } from "child_process";
import fs from "fs";
import path from "path";
import os from "os";
import helmet from "helmet";

// GitHub App Details
dotenv.config(); // Initialize dotenv
const appId = process.env.APP_ID;
const privateKey = process.env.PRIVATE_KEY.replace(/\\n/g, "\n");
const webhookSecret = process.env.WEBHOOK_SECRET;
const port = process.env.PORT || 3000;

// Express setup
const app = express();
app.use(bodyParser.json());
app.use(helmet())

// GitHub JWT for authentication
function generateJWT() {
  const payload = {
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 10 * 60,
    iss: appId,
  };
  return jwt.sign(payload, privateKey, { algorithm: "RS256" });
}

// Verify webhook signature
function verifyWebhook(req, res, next) {
  const signature = req.headers["x-hub-signature-256"];
  const computedSignature = `sha256=${crypto
    .createHmac("sha256", webhookSecret)
    .update(JSON.stringify(req.body))
    .digest("hex")}`;
  if (signature !== computedSignature) {
    return res.status(400).send("Invalid signature");
  }
  next();
}

// Fetch installation access token
async function getInstallationAccessToken(installationId) {
  const jwtToken = generateJWT();
  const url = `https://api.github.com/app/installations/${installationId}/access_tokens`;
  try {
    const response = await axios.post(
      url,
      {},
      {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
          Accept: "application/vnd.github.v3+json",
        },
      }
    );
    return response.data.token;
  } catch (error) {
    console.error("Error fetching installation token:", error.message);
    throw error;
  }
}

// Execute a command and return output
function execCommand(command) {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error || stderr) {
        reject({ stderr, stdout, error });
      } else {
        resolve(stdout);
      }
    });
  });
}

// Function to create a temporary directory
function createTempDir() {
  const tempDir = path.join(process.cwd(), `github-code-checker-${Date.now()}`);
  fs.mkdirSync(tempDir, { recursive: true });
  return tempDir;
}

// Function to download a file
async function downloadFile(url, dest) {
  const writer = fs.createWriteStream(dest);
  const response = await axios.get(url, { responseType: "stream" });
  response.data.pipe(writer);

  return new Promise((resolve, reject) => {
    writer.on("finish", resolve);
    writer.on("error", reject);
  });
}

// Download PR files to temporary directory
async function downloadPRFiles(pull_request, token) {
  const tempDir = createTempDir(); // Create temporary directory
  const files = [];
  const url = pull_request._links.self.href + "/files";

  try {
    const response = await axios.get(url, {
      headers: {
        Authorization: `token ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
    });

    // Loop through each file and download it to the temporary directory
    for (const file of response.data) {
      const fileUrl = file.raw_url; // Get the raw URL of the file
      const filePath = path.join(tempDir, file.filename);

      await downloadFile(fileUrl, filePath); // Download file to temp directory
      files.push({ filename: file.filename, path: filePath });
    }

    console.log("Downloaded files:", files);
    return files;
  } catch (error) {
    console.error("Error fetching or downloading PR files:", error.message);
    throw error;
  }
}

// Check Python files using flake8
async function checkPythonFormatting(files) {
  const comments = [];
  for (const file of files) {
    try {
      try {
        const lintResult = await execCommand(`flake8 ${file.path}`);
      } catch ({ stdout, stderr }) {
        const pattern = /(\/.*github-code-checker-\d+)\//;
        comments.push({
          path: file.filename,
          message: "PEP8 issues detected",
          issues: stdout.trim().replace(pattern, "").split("\n"),
        });
      }
    } catch (error) {
      console.error(`flake8 error for ${file.filename}:`, error);
    }
  }
  return comments;
}

// Check JavaScript files using eslint
async function checkJavaScriptFormatting(files) {
  const comments = [];
  for (const file of files) {
    try {
      const lintResult = await execCommand(
        `eslint --config eslint.config.js ${file.path}`
      );
      console.log("I ran to check Javascript code");
      console.log(lintResult);

      const pattern = /(\/.*github-code-checker-\d+)\//;
      comments.push({
        path: file.filename,
        message: "ESLint issues detected",
        issues: lintResult.trim().replace(pattern, "").split("\n"),
      });
    } catch (error) {
      console.error(`eslint error for ${file.filename}:`, error);
      console.log("Hey! I am here.");
    }
  }
  return comments;
}

// Post comments on PR
async function postPRComments(pull_request, comments, token) {
  const url = `https://api.github.com/repos/${pull_request.base.repo.full_name}/issues/${pull_request.number}/comments`;
  for (const comment of comments) {
    try {
      await axios.post(
        url,
        {
          body: `### 🚨Code formatting issues detected!🚨\n\nFile: \`${
            comment.path
          }\`\n\n**${comment.message}**\n\n${comment.issues.join("\n")}`,
        },
        {
          headers: {
            Authorization: `token ${token}`,
            Accept: "application/vnd.github.v3+json",
          },
        }
      );
    } catch (error) {
      console.error("Error posting comment:", error.message);
    }
  }
}

// Delete temporary directory after processing
function deleteTempDir(tempDir) {
  fs.rmdirSync(tempDir, { recursive: true });
  console.log(`Temporary directory ${tempDir} deleted`);
}

// Handle webhook events
app.post("/webhook", verifyWebhook, async (req, res) => {
  const { action, pull_request, installation } = req.body;
  if (action === "opened" || action === "synchronize") {
    try {
      const token = await getInstallationAccessToken(installation.id);
      const prFiles = await downloadPRFiles(pull_request, token); // Download files

      const pythonFiles = prFiles.filter((file) =>
        file.filename.endsWith(".py")
      );
      const jsFiles = prFiles.filter((file) => file.filename.endsWith(".js"));

      const pythonComments = await checkPythonFormatting(pythonFiles);
      const jsComments = await checkJavaScriptFormatting(jsFiles);

      const allComments = [...pythonComments, ...jsComments];
      if (allComments.length > 0) {
        await postPRComments(pull_request, allComments, token);
      }

      // Delete the temporary directory after processing
        deleteTempDir(path.dirname(prFiles[0].path));
    } catch (error) {
      console.error("Error processing webhook:", error.message);
    }
  }
  res.status(200).send("Webhook processed");
});


app.get("/", (req, res) => {
  // greetings.
  const welcomeMesg = "<h2> You are welcome! </h2>"
  res.send(welcomeMesg);
})


// Start server
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
