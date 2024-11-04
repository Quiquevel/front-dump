import streamlit as st
from functions.utils import tokenparameter, execute_dump
from streamlit_javascript import st_javascript
from functions.dyna import getDynaProblems, getSwitchStatus

async def do_dump_project():
    idToken = st_javascript("localStorage.getItem('idToken');")
    ldap = st_javascript("localStorage.getItem('ldap');")

    st.title('🚨 JAVA Dump 🚨')
    
    optioncluster = None
    optionregion = None
    
    #Integration test with DYNA
    timedyna = "now-30m"
    switchednamespaces = await getSwitchStatus(optioncluster)
    st.markdown("## Dynatrace Open Problems")

    # Get open Dynatrace problems
    problems = await getDynaProblems(timedyna=timedyna,switchednamespaces=switchednamespaces)  # Para cachear la lista de problemas

    if problems:
        delete = False
        # Add a empty option at the beginning
        problems.insert(0, "Select a problem...")  
        selected_problem = st.selectbox("Select an open problem", problems)
    
        # Verify that it is not the default option selected
        if selected_problem != "Select a problem...":
            st.write(f"Selected Problem: {selected_problem}")
            # Extract information and store it in variables
            env_problem = 'pro'
            cluster_problem = selected_problem['cluster']
            region_problem = selected_problem['region']
            namespace_problem = selected_problem['namespace']
            microservice_problem = selected_problem['microservice']
            
            json_object_pod = tokenparameter(env=env_problem, cluster=cluster_problem,region=region_problem,namespace=namespace_problem,microservice=microservice_problem,do_api='podlist',idToken=idToken,ldap=ldap)
            if json_object_pod is not None:
                flat_pod = [x for x in json_object_pod]
                selectpod = st.selectbox('Select Pod', ([''] + flat_pod),key = "pod1")
                if selectpod != '':
                    selectedheap = st.selectbox('Select type', ('', 'HeapDump', 'ThreadDump', 'HeapDump DataGrid', 'ThreadDump DataGrid'),key = "opt_restart_r")
                    execute_dump(optionenv, optioncluster, optionregion, selectnamespace, selectpod, delete, idToken, ldap, do_execute=selectedheap)
        else:
            st.write("No problem selected.")
    else:
        st.write("No open problems found.")
    #Dyna integration END

    delete = st.checkbox('Delete pod after dump?')
    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    with col_a:
        optionenv = st.selectbox('Select Environment', ('pro', 'pre', 'dev'),key = "optionenv")

    col1, col2 = st.columns([1, 2])
    col1, col2, col3 = st.columns(3)

    with col1:
        match optionenv:
            case 'pro':
                optioncluster = st.selectbox('Select Cluster', ('','prodarwin', 'dmzbdarwin', 'azure', 'confluent', 'dmz2bmov', 'probks', 'dmzbbks', 'dmzbazure', 'ocp05azure'),key = "optioncluster1")
            case 'pre':
                optioncluster = st.selectbox('Select Cluster', ('','azure', 'bks', 'ocp05azure'),key = "optioncluster1")
            case 'dev':
                  optioncluster = st.selectbox('Select Cluster', ('','azure', 'bks', 'ocp05azure'),key = "optioncluster1")

    with col2:
        match optionenv:
            case 'dev':
                if 'azure' in optioncluster:
                    optionregion = st.selectbox('Select Region', ('', 'weu1'), key="optioncluster2")
                else:
                    optionregion = st.selectbox('Select Region', ('', 'bo1'), key="optioncluster3")
            case _:
                if optioncluster in ['azure', 'dmzbazure', 'ocp05azure']:
                    optionregion = st.selectbox('Select Region', ('', 'weu1', 'weu2'), key="optioncluster2")
                else:
                    optionregion = st.selectbox('Select Region', ('', 'bo1', 'bo2'), key="optioncluster3")

    with col3:
        if optioncluster != '' and optionregion != '':
            json_object_namespace = tokenparameter(env=optionenv, cluster=optioncluster,region=optionregion,do_api='namespacelist',idToken=idToken,ldap=ldap)
            if json_object_namespace is not None:
                # split namespace list.
                flat_list = [x for x in json_object_namespace]
                selectnamespace = st.selectbox('Select Namespace', ([''] + flat_list),key = "selectnamespace1")
                with col1:
                    if selectnamespace != '':
                        json_object_microservice = tokenparameter(env=optionenv, cluster=optioncluster,region=optionregion,namespace=selectnamespace,do_api='microservicelist',idToken=idToken,ldap=ldap)
                        if json_object_microservice is not None:
                            flat_micro = [x for x in json_object_microservice]
                            selectmicroservice = st.selectbox('Select Microservice', ([''] + flat_micro),key = "selectmicroservice1")                        
                            with col2:
                                if selectmicroservice != '':
                                    json_object_pod = tokenparameter(env=optionenv, cluster=optioncluster,region=optionregion,namespace=selectnamespace,microservice=selectmicroservice,do_api='podlist',idToken=idToken,ldap=ldap)
                                    if json_object_pod is not None:
                                        flat_pod = [x for x in json_object_pod]
                                        selectpod = st.selectbox('Select Pod', ([''] + flat_pod),key = "pod1")
                                        with col3:
                                            if selectpod != '':
                                                selectedheap = st.selectbox('Select type', ('', 'HeapDump', 'ThreadDump', 'HeapDump DataGrid', 'ThreadDump DataGrid'),key = "opt_restart_r")
                                                with col2:
                                                    execute_dump(optionenv, optioncluster, optionregion, selectnamespace, selectpod, delete, idToken, ldap, do_execute=selectedheap)
    st.text('')
    st.text('')
    st.link_button("Help for analysis","https://sanes.atlassian.net/wiki/x/oABatAU",help="Go to documentation with tools and help to do the analysis")
    return delete
