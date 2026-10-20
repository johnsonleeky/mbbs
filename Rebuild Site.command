#!/bin/bash
cd "$(dirname "$0")"

echo "Building split question bank from:"
echo "  /Users/johnson/Desktop/MBBS_QBank_AI_Answers.html"
echo

python3 tools/build_split.py --zip
status=$?

echo
if [ "$status" -ne 0 ]; then
  echo "Build failed. Read the error above."
else
  echo "Done. The site is in the repository root."
  echo "The shareable zip is MBBS_QBank_split.zip"
fi
echo
read -r -p "Press Enter to close..."
exit "$status"
