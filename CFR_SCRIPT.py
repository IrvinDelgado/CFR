#%%
## DEPENDENCIES
from lxml import etree
from bs4 import BeautifulSoup
import requests,re,os
import pandas as pd

## --------------------------Global Variables---------------------
GPM_KEY = ""
CLM_NAMES = ["Title","Section","CFR_LIST","CFR_FLAGGED"]
SPECIFIC_CFR_CHECK = ["43","65","119","120","121","145"]
SPECIFIC_CFR_CHECK_PASS = set() # List of cfr's that will 


## parameter: a url
## returns: XML, converted from the url
def htmlToXML(URL):
    r = requests.get(URL).text
    cleaner = re.sub('&nbsp;',' ',r)
    cleantext = BeautifulSoup(cleaner,"lxml").text
    cleantext = cleantext.replace('<?REVST ?>','')
    cleantext = cleantext.replace('<?REVSE ?>','')
    cleantext = cleantext.replace('<REVCHG>','')
    cleantext = cleantext.replace('</REVCHG>','')
    begin = cleantext.find('<')
    xml = etree.fromstring(cleantext[begin:])
    return xml  

# Generates the characters from `c1` to `c2`, inclusive.
def char_range(c1, c2):
    for c in range(ord(c1), ord(c2)+1):
        yield chr(c)


# Converts roman numeral to integer counterpart
def roman_to_int(s):
        rom_val = {'i': 1, 'v': 5, 'x': 10, 'l': 50}
        int_val = 0
        for i in range(len(s)):
            if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
                int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
            else:
                int_val += rom_val[s[i]]
        return int_val

#Converts integer to roman
def int_to_roman(num):
        val = [50, 40, 10, 9, 5, 4, 1]
        syb = ["l", "xl", "x", "ix", "v", "iv", "i"]
        roman_num = ''
        i = 0
        while  num > 0:
            for _ in range(num // val[i]):
                roman_num += syb[i]
                num -= val[i]
            i += 1
        return roman_num

# During the second report some CFR's are showns as 43.232(a)(2-3),43.232(a)(2)(i-iv)
# For this reason this def takes a CFR and expands it 43.232(a)(2-3) => 43.232(a)(2),43.232(a)(3)
# Parameter : cfr
# returns: list of cfr's 
def expand_cfr(s):
    end_num = s.find('(')
    l = re.findall('\(([^)]+)', s)
    n = s[:end_num]
    f = []
    if not len(l):
        f.append(s)
    for i in l:
        if i.isdigit():
            f.append(f'{n}({l[0]})({i})')
            continue
        if '-' in i:
            r = i.split('-')
            if r[0].isdigit() and r[1].isdigit():#range of #
                for x in range(int(r[0]),int(r[1])+1):
                    f.append(f'{n}({l[0]})({str(x)})')
                continue
            if r[0].isalpha() and r[1].isalpha() and len(r[0])==1 and len(r[1])==1:#range of #
                for x in char_range(r[0],r[1]):
                    f.append(f'{n}({x})')
                continue
            start = roman_to_int(r[0])
            end = roman_to_int(r[1])+1
            for x in range(start,end):
                f.append(f'{n}({l[0]})({l[1]})({int_to_roman(x)})')
            continue
        f.append(n+'('+i+')')
    return f

# Checks if XML part has cfr in the list of CFR's to be analyzed
def does_part_contain_cfr(cfr,part):
    for partName in part.iter("EAR"):
        if cfr in partName.text:
            return True
    return False

# Function which will return all subsections of a cfr input
# For example if cfr = 49
# Then subsections will be 49.121, 49.123(a), 49.145(a)(1)(ii)...
# BREAKING DOWN A CFR
# EXAMPLE 49.145(a)(1)(ii)
# 49.145 => section Title
# (a)    => subsection letter
# (1)    => subsection number
# (ii)   => subsection roman numeral

def get_Subsections_of_CFR(cfr):
    cfr_subsection_list = []
    unknown_subsection = set(['(i)','(v)','(x)']) ##Can be a letter or a roman numeral
    cfr_volume = cfr_belongs_to_volume(cfr)
    path = os.path.join('Title_14_CFR_2020',cfr_volume)
    GOV_XML_FILE = etree.parse(path)
    for part in GOV_XML_FILE.iter("PART"): # EACH CFR is in XML Tags <PART></PART>
        has_cfr = does_part_contain_cfr(cfr,part)
        if has_cfr:
            for section in part.iter("SECTION"): # Will allow to search through CFR Parts in XML if <SECTO> has section part
                for section_Title in section.iter("SECTNO"):
                    if cfr in section_Title.text:
                        subsection_onHold = ''
                        previous_sub = ''
                        sub_num = ''
                        sec_Title = section_Title.text[2:]
                        cfr_subsection_list.append(sec_Title)
                        for para in section.iter("P"):
                            if para.text[0]=='(':
                                end_Parantheses = para.text.find(')')+1
                                #Subsection  = in order ( Letter | # | romanNum ) eg. (3),(e),(iii)
                                #Example 41.2(d)(1)(iv)

                                subsection = para.text[0:end_Parantheses]
                                if end_Parantheses == 0 or subsection[1].isupper(): ##IGNORE (A)and(<i>#<i>)
                                    continue
                                # Since (i) can be interpreted as a either a roman numeral or letter we hold it to see what comes next
                                if subsection in unknown_subsection and not subsection_onHold:
                                    subsection_onHold=subsection

                                elif subsection_onHold and subsection == subsection_onHold:
                                    cfr_subsection_list.append(sec_Title+previous_sub+sub_num+subsection_onHold)
                                    cfr_subsection_list.append(sec_Title+subsection_onHold)
                                    subsection_onHold = ''
                                    previous_sub = subsection
                                elif subsection_onHold and subsection[1].isalpha():
                                    cfr_subsection_list.append(sec_Title+previous_sub+sub_num+subsection_onHold)
                                    cfr_subsection_list.append(sec_Title+previous_sub+sub_num+subsection)
                                    subsection_onHold = ''
                                elif subsection_onHold and subsection[1].isdigit():
                                    cfr_subsection_list.append(sec_Title+subsection_onHold)
                                    cfr_subsection_list.append(sec_Title+subsection_onHold+subsection)
                                    subsection_onHold = ''
                                elif len(subsection)>3:
                                    cfr_subsection_list.append(sec_Title+previous_sub+sub_num+subsection)
                                elif subsection[1].isalpha() and not subsection_onHold:
                                    cfr_subsection_list.append(sec_Title+subsection)
                                    previous_sub = subsection
                                elif subsection[1].isdigit():
                                    cfr_subsection_list.append(sec_Title+previous_sub+subsection)
                                    sub_num = subsection
    return cfr_subsection_list



## parameter: xml
## returns: CFR as well as title of XML 
def get_Section_Data(XML):
    XML_METADATA = [] #METADATA Will be in format [Title, Section]
    CFR_List = []
    for title in XML.iter("TITLE"):
        XML_METADATA.append(title.text)
        break #Since we only need one
    for section in XML.iter("SECTION"):
        XML_METADATA.append(section.get("ATACODE"))
        break
    for cfr in XML.iter("CFR14"): 
        CFR_List.append(cfr.text)
    return [XML_METADATA,CFR_List]

## parameter : cfr
## returns : a cfr in the format ###.###
def clean_cfr(cfr):
    if cfr == None:
        return ''
    cfr_nbr_ends = cfr.find(".")
    cfr_number = cfr
    ## if cfr is ####.AAA just get #### otherwise its already in ####
    if cfr_nbr_ends >= 0:
        cfr_number = cfr[:cfr_nbr_ends]
    try:
        cfr_number = int(cfr_number)
    except ValueError:
        return ''
    return cfr_number

# parameter : cfr
# return : string that contains location of where cfr is located in
def cfr_belongs_to_volume(cfr):
    cfr_number = clean_cfr(cfr)
    if cfr_number == '':
        return ''

    if cfr_number <= 59:
        return "vol1.xml"
    elif cfr_number > 59 and cfr_number <= 109:
        return "vol2.xml"
    elif cfr_number >109 and cfr_number <= 199:
        return "vol3.xml"
    elif cfr_number > 199 and cfr_number <= 1199:
        return "vol4.xml"
    else:
        return "vol5.xml"

# parameter : cfr-> is what is being checked
#             volume -> is where the cfr should be
# return: a boolean if it is there or not
def is_CFR_IN_GOV_CFR(cfr,volume):
    path = os.path.join('Title_14_CFR_2020',volume)
    GOV_XML_FILE = etree.parse(path)
    cfr_number = clean_cfr(cfr)
    for cfr_IN_XML in GOV_XML_FILE.iter("SECTNO"):
        if str(cfr_number) in cfr_IN_XML.text:
            return ''
    return cfr


# parameter : a list of CFR's
# return : a list of CFR's that have discrepencies
def check_CFR(cfr):
    if not cfr:
        return ''
    flagged_cfr_list = ''
    cfr_volume = cfr_belongs_to_volume(cfr)
    if cfr_volume == '':#If cfr is NONE then there is no vol
        return ''
    cfr_exist = is_CFR_IN_GOV_CFR(cfr,cfr_volume)
    if cfr_exist != '':
        return cfr_exist
    return ''


def cfr_in_text_finder(section_XML):
    cfr_text_list = []
    more_text = 30
    for p in section_XML.iter("PARA"):
        if p.text == None or p.text == '':
            break
        for match in re.finditer('14 CFR', p.text):
            st = match.span()[0]
            cfr_text_list.append(p.text[st:st+30])
        for match in re.finditer('14 (CFR)', p.text):
            st = match.span()[0]
            cfr_text_list.append(p.text[st:st+30])
    return cfr_text_list


def main():
    CFR_TABLE = pd.DataFrame(columns = CLM_NAMES)
    CFR_TEXT_TABLE = pd.DataFrame(columns = ['CFR_Section','TEXT'])
    GPM = GPM_KEY.replace("*","SE00-02")
    GPM_TOC_XML = htmlToXML(GPM)
    for section in GPM_TOC_XML.iter("REFINT"):
        section_REFID = section.get("REFID")
        if section_REFID == '':##Some are blank so skip them
            continue
        section_URL = GPM_KEY.replace("*",section_REFID)
        section_XML = htmlToXML(section_URL)
        section_DATA = get_Section_Data(section_XML)

        #Check CFR in TEXT and append to Report 3
        list_cfr_in_text = cfr_in_text_finder(section_XML)
        for cfr_text in  list_cfr_in_text:
            zipObject = zip(['CFR_Section','TEXT'],[section_DATA[0][1]+'_',cfr_text])
            dictObj = dict(zipObject)
            CFR_TEXT_TABLE = CFR_TEXT_TABLE.append([dictObj],ignore_index=True)
        

        section_XML_METADATA = section_DATA[0] #[Title, Section]
        section_CFR_LIST = section_DATA[1]
        FLAGGED_CFR = ''
        for cfr in section_CFR_LIST:
            FLAGGED_CFR = check_CFR(cfr)
            if cfr and cfr!='' and cfr.replace(' ','') in CFR_CHECK:
                SPECIFIC_CFR_CHECK_PASS.add(cfr) 
            data = [section_XML_METADATA[0],section_XML_METADATA[1]+'_',cfr,FLAGGED_CFR]       
            zipObject = zip(CLM_NAMES,data)
            dictObj = dict(zipObject)
            CFR_TABLE = CFR_TABLE.append([dictObj],ignore_index=True)



    path = os.path.join('Report_1')
    CFR_TABLE.to_csv(path+'.csv',index=False)

    path = os.path.join('Report_3')
    CFR_TEXT_TABLE.drop_duplicates(inplace=True)
    CFR_TEXT_TABLE.to_csv(path+'.csv',index=False)

    SPECIFIC_CFR_TABLE = pd.DataFrame(columns = ['CFR','IN_MANUAL','IS_BASE'])
    for cfr in CFR_CHECK:
        in_Manual = False
        is_Base = False
        if '(' not in cfr:
            is_Base = True
        if cfr in SPECIFIC_CFR_CHECK_PASS:
            in_Manual = True
        zipObject = zip(['CFR','IN_MANUAL','IS_BASE'],[cfr,in_Manual,is_Base])
        dictObj = dict(zipObject)
        SPECIFIC_CFR_TABLE = SPECIFIC_CFR_TABLE.append([dictObj],ignore_index=True)
        
    path = os.path.join('Report_2')
    SPECIFIC_CFR_TABLE.to_csv(path+'.csv',index=False)

    return CFR_TABLE

# %%
CFR_CHECK = set()
for cfr in SPECIFIC_CFR_CHECK:
    CFR_CHECK.update(get_Subsections_of_CFR(cfr))
main()

#%%


# %%
