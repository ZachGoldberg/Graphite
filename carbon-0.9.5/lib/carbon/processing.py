import traceback, re, time
import simplejson as json

# Cache the compiled regular expressions, 30%+ perf. boost
precompiled_regex = {}
template_data = {}
bucket_templates = []
rollup_templates = []
bucket_temp_parts = []
bucket_cache = {}
loaded = False

def loadTemplateData():
  global bucket_templates, rollup_templates
  global bucket_temp_parts, bucket_cache, loaded

  bucket_templates = load_templates("bucket_templates.json")  
  rollup_templates = load_templates("rollup_templates.json")

  bucket_cache = {}
  for template, buckets in bucket_templates:
    for bucket in buckets:
      bucket_cache[bucket] = bucket.split(".")

  bucket_temp_parts = []
  for template, buckets in bucket_templates:
    bucket_temp_parts.append(template.split("."))
 
  loaded = True

def processMetric(path):
  global bucket_templates, rollup_templates
  global bucket_temp_parts, bucket_cache, loaded

  if not loaded:
    loadTemplateData()

  new_paths = []

  tempnum = 0
  bucket_match = False
  for template, buckets in bucket_templates:    
    new_path = template_match(template, bucket_temp_parts[tempnum], 
                              len(bucket_temp_parts[tempnum]), path, replace_dollar_signs=False)
    tempnum += 1

    if new_path:
      bucket_match = True
      path_parts = path.split(".")
      
      # This line matches a bucket template.  Add a new line for each bucket
      for bucket in buckets:
        bucket_parts = bucket_cache[bucket]

        # Included for invitemedia test mode
        if path.startswith("test."):
          new_path = ["test"]
        else:
          new_path = []

        for index, bucket_part in enumerate(bucket_parts):
          if "*" in bucket_part:
            new_path.append(path_parts[index])
          else:
            new_path.append(bucket_part)
        
        new_paths.append('.'.join(new_path))

      break # Any one line should really only match one bucket template
  
  template_matches = []
  # For each template we need go through all of the input and aggregate on that template
  for template in rollup_templates:
    template_parts = template.split(".")
    template_parts_len = len(template_parts)
    new_path = template_match(template, template_parts, template_parts_len, path, replace_dollar_signs=True)
    
    if new_path:
      new_path = "rollup_data." + new_path
      new_paths.append(new_path)
      new_paths.append(path)

  new_paths = list(set(new_paths))

  if not new_paths and not bucket_match:
    new_paths = [path]

  return new_paths

def load_templates(filename):
  """
  Opens a json file and returns the deserialized data
  """
  global template_data
  if filename in template_data:
    return template_data[filename]

  try:
    f = open(filename)
    data = '\n'.join(f.readlines())
    template_data[filename] = json.loads(data)
  except:
    print "Error loading templates.  Trying to use file %s" % filename
    traceback.print_exc()

  return template_data.get(filename, [])

def template_match(template, template_parts, template_parts_len, path, replace_dollar_signs=False):
  """
  Checks to see if "path" matches the provided template
  If so generate a new path appropriatly and return it
  else return None

  New paths are either the old path (replace_dollar_sign=False)
  or a new path with the following rule: (replace_dollar_sign=True)
  * For any node in the path which contains a dollar sign in the corresponding
  node in the template's path replace that node in the path with the node from the template.

  This is what does the 'grouping' or 'rolling up' of points into paths with dollar signs.
  """

  if (path.count(".") + 1) != template_parts_len:
    return None

  global precompiled_regex
  if template not in precompiled_regex:
    # Compute the new regx and cache it in the global variable
    regx_str = "^%s$" % template.replace(".", "\.")
    regx_str = regx_str.replace("*", ".*")
    regx_str = regx_str.replace("$", ".*")
    precompiled_regex[template] = re.compile(regx_str)

  regx = precompiled_regex[template]
  if not regx.match(path):
    return None
  else:
    if replace_dollar_signs:
      parts = path.split(".")
      len_parts = len(parts)
    
      new_path = []
      for i in xrange(0, len_parts):
        if "$" in template_parts[i]:
          new_path.append(template_parts[i])
        else:
          new_path.append(parts[i])
      return '.'.join(new_path)
    else:
      return path
