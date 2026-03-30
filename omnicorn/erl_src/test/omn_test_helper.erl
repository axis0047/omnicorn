-module(omn_test_helper).

%% Test helper for initializing Mnesia and other dependencies
-export([setup_mnesia/0, cleanup_mnesia/0]).

setup_mnesia() ->
    %% Stop Mnesia if running
    catch application:stop(mnesia),
    
    %% Delete ETS tables first (before starting Mnesia)
    catch ets:delete(active_actors),
    catch ets:delete(omnicorn_cache),
    
    %% Start fresh
    application:start(mnesia),
    
    %% Delete Mnesia tables if they exist (force recreate)
    catch mnesia:delete_table(omn_sagas),
    catch mnesia:delete_table(omn_activities),
    timer:sleep(50),
    
    %% Create tables
    mnesia:create_table(omn_sagas, [
        {attributes, [id, name, step, data]},
        {disc_copies, [node()]}
    ]),
    
    mnesia:create_table(omn_activities, [
        {attributes, [id, name, payload, retries]},
        {disc_copies, [node()]}
    ]),
    
    %% Wait for tables
    mnesia:wait_for_tables([omn_sagas, omn_activities], 5000),
    
    %% Create ETS tables
    ets:new(active_actors, [named_table, public, set]),
    ets:new(omnicorn_cache, [named_table, public, set]),
    
    ok.

cleanup_mnesia() ->
    %% Clean up tables
    catch mnesia:clear_table(omn_sagas),
    catch mnesia:clear_table(omn_activities),
    catch ets:delete(active_actors),
    catch ets:delete(omnicorn_cache),
    catch application:stop(mnesia),
    ok.
